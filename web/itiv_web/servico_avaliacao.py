# -*- coding: utf-8 -*-
"""Inferência e HTML de resultado (mesma UI do avaliador original)."""
from __future__ import annotations

import html
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from itiv_web.config import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, R_TERRA, VERSAO_MODELO
from itiv_web.ipca import deflacionar_valores
from itiv_web.models import Cadastro, Transmissao
from itiv_web.runtime import STATE

_CODIGO = Path(__file__).resolve().parents[2] / "Modelo_Apartamentos_Aprovado" / "codigo"
if str(_CODIGO) not in sys.path:
    sys.path.insert(0, str(_CODIGO))

import apartamentos_lib as aplib  # noqa: E402
from inscricao_relativa import anexar_inscricao_relativa  # noqa: E402


def fmt_rs(v) -> str:
    try:
        f = float(v)
        if not np.isfinite(f):
            return "—"
        s = f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return "R$ " + s
    except (TypeError, ValueError):
        return "—"


def fmt_num(v, dec: int = 0) -> str:
    try:
        f = float(v)
        if not np.isfinite(f):
            return "—"
        s = f"{f:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except (TypeError, ValueError):
        return "—"


def fmt_int(v) -> str:
    try:
        f = float(v)
        if not np.isfinite(f):
            return "—"
        return str(int(f))
    except (TypeError, ValueError):
        return "—"


def fmt_data(v) -> str:
    try:
        return pd.to_datetime(v).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "—"


def _tx_dict(row: Transmissao) -> dict:
    return {
        "sq": row.sq,
        "cdinscricaoimob": row.cdinscricaoimob,
        "tipologia": row.tipologia,
        "data_transacao": row.data_transacao,
        "vltransacao": row.vltransacao,
        "vlitiv": row.vlitiv,
        "vlvenalcadastro": row.vlvenalcadastro,
        "vlvenalcorrigido": row.vlvenalcorrigido,
        "vltransacao_deflacionado": row.vltransacao_deflacionado,
        "var_tendencia": row.var_tendencia,
        "vlareausopriv": row.vlareausopriv,
        "nupavimentos": row.nupavimentos,
        "nupavimentounidade": row.nupavimentounidade,
        "cdsetorfiscal": row.cdsetorfiscal,
        "vlcoordgeox": row.vlcoordgeox,
        "vlcoordgeoy": row.vlcoordgeoy,
        "latitude": row.latitude,
        "longitude": row.longitude,
    }


def _idade_na_transacao(inscricao, data_ref) -> tuple[float, int, int]:
    insc = pd.to_numeric(inscricao, errors="coerce")
    ano_tx = pd.to_datetime(data_ref, errors="coerce")
    ano_tx = int(ano_tx.year) if pd.notna(ano_tx) else 2026
    if pd.isna(insc):
        return STATE.idade_mediana_treino, 1, 0
    ano_const = STATE.nascimento_map.get(int(insc))
    if ano_const is None or (isinstance(ano_const, float) and np.isnan(ano_const)):
        return STATE.idade_mediana_treino, 1, 0
    ano_const = float(ano_const)
    if not (1500 <= ano_const <= ano_tx):
        return STATE.idade_mediana_treino, 0, 1
    idade = ano_tx - ano_const
    if idade < 0:
        return STATE.idade_mediana_treino, 0, 1
    return float(idade), 0, 0


def _preparar_features(info: dict, sq_para_var_tendencia: int | None) -> pd.DataFrame:
    area = pd.to_numeric(info.get("vlareausopriv"), errors="coerce")
    if not (pd.notna(area) and area > 0):
        return pd.DataFrame()
    log_area = float(np.log(area))

    pav = pd.to_numeric(info.get("nupavimentos"), errors="coerce")
    pav = pav if pd.notna(pav) and pav > 0 else np.nan

    andar = pd.to_numeric(info.get("nupavimentounidade"), errors="coerce")
    flag_andar_ausente = int(pd.isna(andar) or andar <= 0)
    andar_unidade = float(andar) if pd.notna(andar) and andar > 0 else 0.0

    insc = pd.to_numeric(info.get("cdinscricaoimob"), errors="coerce")
    data_ref = info.get("data_transacao")
    idade_imp, flag_ausente, flag_invalido = _idade_na_transacao(insc, data_ref)

    params = pd.DataFrame(
        [
            {
                "LOG_AREA": log_area,
                "NUPAVIMENTOS": pav,
                "ANDAR_UNIDADE": andar_unidade,
                "FLAG_ANDAR_AUSENTE": flag_andar_ausente,
                "CDSETORFISCAL": info.get("cdsetorfiscal"),
                "VLCOORDGEOX": pd.to_numeric(info.get("vlcoordgeox"), errors="coerce"),
                "VLCOORDGEOY": pd.to_numeric(info.get("vlcoordgeoy"), errors="coerce"),
                "CDINSCRICAOIMOB": insc,
                "IDADE_NA_TRANSACAO_IMP": idade_imp,
                "FLAG_ANO_AUSENTE": flag_ausente,
                "FLAG_ANO_INVALIDO": flag_invalido,
            }
        ]
    )

    if sq_para_var_tendencia is not None:
        vt = info.get("var_tendencia")
        if vt is not None and pd.notna(vt):
            params["VAR_TENDENCIA"] = float(vt)
        else:
            achado = STATE.pool[STATE.pool["SQTRANSMISSAO"] == sq_para_var_tendencia]
            if not achado.empty and "VAR_TENDENCIA" in achado.columns:
                params["VAR_TENDENCIA"] = float(achado.iloc[0]["VAR_TENDENCIA"])
            else:
                params["VAR_TENDENCIA"] = float(STATE.fill_medianas.get("VAR_TENDENCIA", 0.0))
    else:
        params["VAR_TENDENCIA"] = 0.0

    params = anexar_inscricao_relativa(params, STATE.stats_setor)
    return params


def _montar_X_producao(params: pd.DataFrame) -> pd.DataFrame:
    X = params[STATE.features_producao].copy()
    X["CDSETORFISCAL"] = pd.Categorical(X["CDSETORFISCAL"], categories=STATE.categorias_setor)
    for col, med in STATE.fill_medianas.items():
        if col in X.columns:
            X[col] = X[col].fillna(med)
    if "KNN_PROXY" in X.columns:
        X["KNN_PROXY"] = X["KNN_PROXY"].fillna(STATE.mediana_proxy)
    return X


def _memoria_calculo_lgbm(x_row: pd.DataFrame) -> list[dict]:
    try:
        import shap

        explainer = shap.TreeExplainer(STATE.modelo_lgbm)
        shap_vals = explainer.shap_values(x_row)[0]
    except Exception:  # noqa: BLE001
        return []
    total_abs = np.sum(np.abs(shap_vals)) or 1.0
    rotulos = {
        "LOG_AREA": "Area privativa",
        "NUPAVIMENTOS": "Pavimentos do predio",
        "ANDAR_UNIDADE": "Andar da unidade",
        "FLAG_ANDAR_AUSENTE": "Andar nao informado",
        "VAR_TENDENCIA": "Defasagem temporal",
        "VLCOORDGEOX": "Localizacao (X)",
        "VLCOORDGEOY": "Localizacao (Y)",
        "CDSETORFISCAL": "Setor fiscal",
        "KNN_PROXY": "Referencia de vizinhanca (R$/m2)",
        "IDADE_NA_TRANSACAO_IMP": "Idade do imovel (anos)",
        "FLAG_ANO_AUSENTE": "Ano de construcao ausente",
        "FLAG_ANO_INVALIDO": "Ano de construcao invalido",
        "LOG_INSCRICAO_REL": "Inscricao relativa no setor",
        "RANK_INSCRICAO_SETOR": "Posicao da inscricao no setor",
    }
    linhas = []
    for col, sv in zip(x_row.columns, shap_vals):
        linhas.append(
            {
                "parametro": rotulos.get(col, col),
                "contribuicao_pct": f"{sv / total_abs * 100:+.1f}%",
                "impacto": "aumenta o valor" if sv > 0 else "reduz o valor" if sv < 0 else "neutro",
            }
        )
    linhas.sort(key=lambda c: abs(float(c["contribuicao_pct"].rstrip("%"))), reverse=True)
    return linhas


def _prever(params: pd.DataFrame) -> dict:
    knn_proxy = aplib.calcular_knn_proxy(STATE.pool, params, k=aplib.K_VIZINHOS)
    params = params.copy()
    params["KNN_PROXY"] = knn_proxy
    X = _montar_X_producao(params)
    log_pred = STATE.modelo_lgbm.predict(X)[0]
    previsto_lgbm = float(np.exp(log_pred))
    ic_inf = previsto_lgbm * float(STATE.ic80_inf)
    ic_sup = previsto_lgbm * float(STATE.ic80_sup)
    previsto_hed = float(np.exp(aplib.prever_hedonico(STATE.modelo_hed, STATE.colunas_hed, params)[0]))
    contrib = _memoria_calculo_lgbm(X.iloc[[0]])
    return {
        "previsto_lgbm": previsto_lgbm,
        "previsto_hedonico": previsto_hed,
        "ic_inf": ic_inf,
        "ic_sup": ic_sup,
        "memoria": contrib,
    }


def _lat_lon(info: dict) -> tuple[float, float]:
    lat = pd.to_numeric(info.get("latitude"), errors="coerce")
    lon = pd.to_numeric(info.get("longitude"), errors="coerce")
    if np.isfinite(lat) and np.isfinite(lon):
        return float(lat), float(lon)
    x = pd.to_numeric(info.get("vlcoordgeox"), errors="coerce")
    y = pd.to_numeric(info.get("vlcoordgeoy"), errors="coerce")
    if pd.notna(x) and pd.notna(y) and x != 0 and y != 0 and STATE.utm2geo is not None:
        lon_c, lat_c = STATE.utm2geo.transform(float(x), float(y))
        if LAT_MIN <= lat_c <= LAT_MAX and LON_MIN <= lon_c <= LON_MAX:
            return float(lat_c), float(lon_c)
    return float("nan"), float("nan")


def comparaveis(session: Session, lat: float, lon: float, data, sq_excluir: int | None) -> list[dict]:
    if not (np.isfinite(lat) and np.isfinite(lon)) or data is None:
        return []
    dt = pd.to_datetime(data)
    inicio = (dt - pd.DateOffset(months=36)).date()
    fim = dt.to_period("M").to_timestamp().date()
    stmt = select(Transmissao).where(
        Transmissao.tipologia == "Apartamento",
        Transmissao.data_transacao.is_not(None),
        Transmissao.data_transacao >= inicio,
        Transmissao.data_transacao < fim,
        Transmissao.latitude.is_not(None),
        Transmissao.longitude.is_not(None),
    )
    if sq_excluir is not None:
        stmt = stmt.where(Transmissao.sq != sq_excluir)
    # recorte espacial ~15 km para não trazer a base inteira
    margem = 0.15
    stmt = stmt.where(
        and_(
            Transmissao.latitude.between(lat - margem, lat + margem),
            Transmissao.longitude.between(lon - margem, lon + margem),
        )
    )
    rows = session.execute(stmt).scalars().all()
    if len(rows) < 3:
        return []
    coords = np.radians([[r.latitude, r.longitude] for r in rows])
    tree = BallTree(coords, metric="haversine")
    k = min(15, len(rows))
    dist, idx = tree.query(np.radians([[lat, lon]]), k=k)
    out = []
    for d, i in zip(dist[0], idx[0]):
        v = rows[int(i)]
        area = v.vlareausopriv
        valor = v.vltransacao_deflacionado if v.vltransacao_deflacionado else v.vltransacao
        m2 = (valor / area) if area and area > 0 and valor else np.nan
        out.append(
            {
                "sq": int(v.sq),
                "data": fmt_data(v.data_transacao),
                "dist_m": round(float(d) * R_TERRA),
                "area": round(float(area), 1) if area and np.isfinite(area) else 0,
                "valor": float(valor) if valor and np.isfinite(valor) else 0.0,
                "m2": round(float(m2), 2) if np.isfinite(m2) else 0.0,
                "lat": round(float(v.latitude), 5),
                "lon": round(float(v.longitude), 5),
            }
        )
    return out


def mapa_html(lat: float, lon: float, comps: list[dict]) -> str:
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return ""

    def sv_img(la: float, lo: float) -> str:
        return (
            f'<img src="/streetview?lat={la}&lon={lo}" '
            f'style="width:260px;height:130px;object-fit:cover;border-radius:4px;margin-top:6px;display:block">'
        )

    popup_avaliado = "<b>Imovel avaliado</b>" + sv_img(lat, lon)
    return f"""
    <h2>Mapa — imovel e comparaveis (transacoes reais)</h2>
    <div id="mapa" style="height:480px;border:1px solid #ccc;border-radius:8px;"></div>
    <p class="nota" style="border:0;margin-top:6px">
      Marcador: imovel avaliado. Circulo verde: raio de 500 m.
      Azul: {len(comps)} comparaveis (transacoes ITIV de apartamentos). Nao ha uso de anuncios.</p>
    <script>
    const mapa = L.map('mapa').setView([{lat}, {lon}], 16);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
      {{ attribution: 'OpenStreetMap', maxZoom: 19 }}).addTo(mapa);
    L.marker([{lat}, {lon}]).bindPopup({json.dumps(popup_avaliado)}).addTo(mapa).openPopup();
    L.circle([{lat}, {lon}], {{ radius: 500, color: '#2e7d32', weight: 2, fillOpacity: 0.06 }}).addTo(mapa);
    const comps = {json.dumps(comps, ensure_ascii=False)};
    comps.forEach(c => {{
      const svImg = '<img src="/streetview?lat='+c.lat+'&lon='+c.lon+'" style="width:260px;height:130px;object-fit:cover;border-radius:4px;margin-top:6px;display:block">';
      L.circleMarker([c.lat, c.lon],
        {{ radius: 7, color: '#1565c0', weight: 1, fillOpacity: 0.7 }})
        .bindPopup('<b>Comparavel SQ ' + c.sq + '</b><br>Vendido em ' + c.data +
                   '<br>Declarado corrigido: R$ ' + c.valor.toLocaleString('pt-BR') +
                   svImg).addTo(mapa);
    }});
    </script>
    """


def _bloco_endereco(lat: float, lon: float) -> str:
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return ""
    return f"""
    <h2>Localizacao</h2>
    <div id="bloco-endereco" style="background:white;border:1px solid #ddd;border-radius:8px;
         padding:14px 18px;font-size:1em;color:#333;">
      <span id="geo-status" style="color:#888">Buscando endereco...</span>
    </div>
    <script>
    (function() {{
      fetch('/geocode?lat={lat}&lon={lon}&_=' + Date.now())
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{
          var el = document.getElementById('geo-status');
          if (d.endereco) {{
            el.style.color = '#1a3a5c'; el.style.fontWeight = 'bold'; el.textContent = d.endereco;
          }} else {{
            el.style.color = '#c62828';
            el.textContent = 'Endereco indisponivel (Google: ' + (d.status || 'sem resposta') +
              (d.erro ? ' — ' + d.erro : '') + ').';
          }}
        }})
        .catch(function() {{ document.getElementById('geo-status').textContent = 'Erro ao buscar endereco.'; }});
    }})();
    </script>
    """


def _tabela_comparaveis(comps: list[dict]) -> str:
    if not comps:
        return ""
    linhas = "".join(
        f"<tr><td>{c['sq']}</td><td>{c['data']}</td><td style='text-align:right'>{fmt_num(c['dist_m'])} m</td>"
        f"<td style='text-align:right'>{fmt_num(c['area'], 1)}</td>"
        f"<td style='text-align:right'>{fmt_rs(c['valor'])}</td>"
        f"<td style='text-align:right'>{fmt_rs(c['m2'])}</td></tr>"
        for c in comps
    )
    mediana = np.median([c["m2"] for c in comps if c["m2"] > 0]) if comps else 0
    return f"""
    <h2>Os {len(comps)} comparaveis (apartamentos vendidos antes, ate 36 meses, transacoes reais)</h2>
    <table><tr><th>SQ</th><th>Data</th><th>Distancia</th><th>Area m2</th><th>Valor declarado corrigido</th><th>R$/m2</th></tr>
    {linhas}</table>
    <p>Mediana R$/m2 dos comparaveis: <strong>{fmt_rs(mediana)}</strong></p>
    """


def _mem_html(mem: list[dict]) -> str:
    if not mem:
        return ""
    linhas = "".join(
        f"<tr><td>{html.escape(m['parametro'])}</td>"
        f"<td style='text-align:right'>{m['contribuicao_pct']}</td><td>{m['impacto']}</td></tr>"
        for m in mem
    )
    return f"""
    <h3>Memoria de calculo (modelo LightGBM, SHAP)</h3>
    <table><tr><th>Parametro</th><th>Contribuicao</th><th>Impacto</th></tr>{linhas}</table>
    """


def avaliar_sq(session: Session, sq: int) -> str:
    row = session.get(Transmissao, sq)
    if row is None:
        return f"<p class='erro'>SQ {sq} nao encontrado na base.</p>"
    info = _tx_dict(row)
    if str(info.get("tipologia") or "") != "Apartamento":
        return (
            "<p class='erro'>Este avaliador cobre apenas <b>Apartamento</b> com compra e venda "
            f"registrada. Tipologia encontrada: {html.escape(str(info.get('tipologia') or ''))}.</p>"
        )
    params = _preparar_features(info, sq_para_var_tendencia=sq)
    if params.empty:
        return "<p class='erro'>Transacao sem area privativa valida — nao ha como calcular o modelo.</p>"
    pred = _prever(params)
    lat, lon = _lat_lon(info)
    data_transacao = info.get("data_transacao")
    declarado = pd.to_numeric(info.get("vltransacao_deflacionado"), errors="coerce")
    rotulo_declarado = "Declarado (corrigido)"
    if not (np.isfinite(declarado) and declarado > 0):
        vl_bruto = pd.to_numeric(info.get("vltransacao"), errors="coerce")
        if pd.notna(vl_bruto) and vl_bruto > 0 and data_transacao is not None:
            declarado = float(
                deflacionar_valores(
                    pd.Series([vl_bruto]),
                    pd.Series([data_transacao]),
                    STATE.ipca,
                ).iloc[0]
            )
            rotulo_declarado = "Declarado (atualizado IPCA)"
    vva = pd.to_numeric(info.get("vlvenalcadastro"), errors="coerce")
    area_mod = pd.to_numeric(info.get("vlareausopriv"), errors="coerce")
    m2_declarado = (
        declarado / area_mod
        if np.isfinite(area_mod) and area_mod > 0 and np.isfinite(declarado) and declarado > 0
        else np.nan
    )
    comps = comparaveis(session, lat, lon, data_transacao, sq_excluir=sq)
    dif_pct = (
        (pred["previsto_lgbm"] - declarado) / declarado * 100
        if declarado and declarado > 0
        else float("nan")
    )
    versao = STATE.versao or VERSAO_MODELO
    assunto = f"Avaliacao ITIV (idade+rel) - SQ {sq}"
    corpo_mail = (
        f"Avaliacao do imovel SQ {sq} (inscricao {info.get('cdinscricaoimob', '')}): "
        f"declarado {fmt_rs(declarado)}, estimativa do modelo {fmt_rs(pred['previsto_lgbm'])}."
    )
    mailto = f"mailto:?subject={quote(assunto)}&body={quote(corpo_mail)}"
    return f"""
    <div class="acoes">
      <button class="btn-pdf" onclick="document.title='Avaliacao_ITIV_SQ_{sq}'; window.print()">Salvar em PDF</button>
      <a class="btn-mail" href="{mailto}">Enviar por e-mail</a>
    </div>
    <h2>Imovel — SQ {sq}</h2>
    <table class="info">
      <tr><th>Inscricao</th><td>{html.escape(str(info.get('cdinscricaoimob', '')))}</td>
          <th>Tipologia</th><td>Apartamento</td></tr>
      <tr><th>Setor fiscal</th><td>{fmt_int(info.get('cdsetorfiscal', ''))}</td>
          <th>Data</th><td>{fmt_data(info.get('data_transacao'))}</td></tr>
      <tr><th>Area privativa</th><td>{fmt_num(area_mod, 1)} m2</td>
          <th>Andar</th><td>{fmt_int(info.get('nupavimentounidade'))} de {fmt_int(info.get('nupavimentos'))}</td></tr>
    </table>
    {_bloco_endereco(lat, lon)}
    <h2>Avaliacao (modelo com idade — promovido 26/08/2026)</h2>
    <div class="cards">
      <div class="card"><div class="rotulo">{rotulo_declarado}</div><div class="valor">{fmt_rs(declarado)}</div></div>
      <div class="card"><div class="rotulo">Preco declarado (R$/m2)</div><div class="valor">{fmt_rs(m2_declarado)}</div></div>
      <div class="card"><div class="rotulo">VVA</div><div class="valor">{fmt_rs(vva)}</div></div>
      <div class="card destaque"><div class="rotulo">Estimativa do modelo (LightGBM)</div><div class="valor">{fmt_rs(pred['previsto_lgbm'])}</div>
        <div class="sub">IC 80%: {fmt_rs(pred['ic_inf'])} a {fmt_rs(pred['ic_sup'])}</div></div>
      <div class="card"><div class="rotulo">Segunda opiniao (hedonica)</div><div class="valor">{fmt_rs(pred['previsto_hedonico'])}</div></div>
    </div>
    <p>Diferenca estimativa vs declarado: <strong>{
        f"{fmt_num(abs(dif_pct), 1)}% {'acima' if dif_pct >= 0 else 'abaixo'} do declarado"
        if np.isfinite(dif_pct) else "— (valor declarado ausente ou zero)"}</strong></p>
    {_mem_html(pred["memoria"])}
    {_tabela_comparaveis(comps)}
    {mapa_html(lat, lon, comps)}
    <p class="nota">Escopo: Apartamento com compra e venda registrada (unico tipo coberto pelo modelo).
    Este avaliador NAO usa dados de anuncios — apenas transacoes reais (ITIV) entram no calculo e nos comparaveis.<br>
    Modelo: LightGBM com idade do imovel e inscricao relativa no setor ({html.escape(versao)});
    parametros base + idade + posicao cadastral no setor fiscal.
    IC 80% calculado sobre a distribuicao real de erro no holdout do candidato promovido.<br>
    A classificacao e subsidio tecnico — a decisao e do auditor fiscal.<br>
    <strong>Metodologia de correcao monetaria:</strong> valores atualizados pelo IPCA/IBGE (serie 433, SGS/BCB).</p>
    """


def buscar(session: Session, q: str) -> str:
    q = q.strip().replace(".", "").replace("-", "")
    if not q.isdigit():
        return "<p class='erro'>Digite um numero de SQ ou inscricao imobiliaria.</p>"
    n = int(q)
    if session.get(Transmissao, n) is not None:
        return avaliar_sq(session, n)
    achados = (
        session.query(Transmissao)
        .filter(Transmissao.cdinscricaoimob == n)
        .order_by(Transmissao.data_transacao.desc())
        .all()
    )
    if not achados:
        return f"<p class='erro'>Nenhum SQ nem inscricao = {n}.</p>"
    if len(achados) == 1:
        return avaliar_sq(session, int(achados[0].sq))
    linhas = "".join(
        f"<tr><td><a href='/avaliar?q={int(r.sq)}'>{int(r.sq)}</a></td>"
        f"<td>{fmt_data(r.data_transacao)}</td>"
        f"<td>{html.escape(str(r.tipologia or ''))}</td>"
        f"<td style='text-align:right'>{fmt_rs(r.vltransacao)}</td></tr>"
        for r in achados
    )
    return f"""<h2>Inscricao {n}: {len(achados)} transmissoes — escolha uma</h2>
    <table><tr><th>SQ</th><th>Data</th><th>Tipologia</th><th>Valor declarado</th></tr>{linhas}</table>"""


def avaliar_cadastro(session: Session, inscricao: int) -> str:
    info_row = session.get(Cadastro, inscricao)
    if info_row is None:
        return f"<p class='erro'>Inscricao {inscricao} nao encontrada no cadastro.</p>"
    if "apartamento" not in str(info_row.dssubunidade or "").lower():
        return (
            "<p class='erro'>Este avaliador cobre apenas <b>Apartamento</b>. "
            f"Tipologia no cadastro: {html.escape(str(info_row.dssubunidade or ''))}.</p>"
        )
    info = {
        "sq": -int(inscricao),
        "cdinscricaoimob": int(inscricao),
        "tipologia": str(info_row.dssubunidade or ""),
        "vlareausopriv": info_row.vlareausopriv,
        "nupavimentounidade": info_row.nupavimentounidade,
        "nupavimentos": info_row.nupavimentos,
        "cdsetorfiscal": info_row.cdsetorfiscal,
        "vlcoordgeox": info_row.vlcoordgeox,
        "vlcoordgeoy": info_row.vlcoordgeoy,
        "latitude": info_row.latitude,
        "longitude": info_row.longitude,
        "data_transacao": date.today(),
        "var_tendencia": 0.0,
    }
    params = _preparar_features(info, sq_para_var_tendencia=None)
    if params.empty:
        return "<p class='erro'>Imovel sem area privativa valida no cadastro.</p>"
    pred = _prever(params)
    lat, lon = _lat_lon(info)
    vvenal = pd.to_numeric(info_row.vlvenalcadastro, errors="coerce")
    prev = pred["previsto_lgbm"]
    if np.isfinite(prev) and np.isfinite(float(vvenal or 0)) and float(vvenal) > 0:
        dif_pct = (prev - float(vvenal)) / float(vvenal) * 100
        if abs(dif_pct) <= 20:
            badge_cor, badge_txt = "#2e7d32", "COMPATIVEL"
        elif dif_pct > 20:
            badge_cor, badge_txt = "#1565c0", "VENAL DEFASADO (mercado acima)"
        else:
            badge_cor, badge_txt = "#e65100", "VENAL ACIMA DO MERCADO"
        dif_html = f"<span style='color:{badge_cor};font-weight:bold'>{dif_pct:+.1f}%</span>"
    else:
        badge_cor, badge_txt, dif_html = "#555", "SEM COMPARACAO", "—"
        dif_pct = float("nan")
    comps = comparaveis(session, lat, lon, date.today(), sq_excluir=None) if np.isfinite(lat) else []
    bloco_end = _bloco_endereco(lat, lon)
    if not bloco_end:
        end_txt = f"{info_row.dslogradouro or ''}, {info_row.nuporta or ''} — CEP {info_row.cdcep or ''}".strip(", ")
        bloco_end = (
            f"<h2>Localizacao</h2><div style='background:white;border:1px solid #ddd;"
            f"border-radius:8px;padding:14px 18px'><b>{html.escape(end_txt)}</b></div>"
        )
    versao = STATE.versao or VERSAO_MODELO
    assunto = f"Avaliacao Cadastral ITIV (idade+rel) - Inscricao {inscricao}"
    corpo_mail = (
        f"Avaliacao do imovel inscricao {inscricao} (sem transmissao): "
        f"valor venal {fmt_rs(vvenal)}, estimativa do modelo {fmt_rs(prev)}, situacao {badge_txt}."
    )
    mailto = f"mailto:?subject={quote(assunto)}&body={quote(corpo_mail)}"
    return f"""
    <div class="acoes">
      <button class="btn-pdf" onclick="document.title='Avaliacao_Cadastral_{inscricao}'; window.print()">Salvar em PDF</button>
      <a class="btn-mail" href="{mailto}">Enviar por e-mail</a>
    </div>
    <h2>Imovel — Inscricao {inscricao} <small style="font-size:0.6em;color:#888">(cadastro — sem transmissao registrada)</small></h2>
    <table class="info">
      <tr><th>Inscricao</th><td>{inscricao}</td><th>Tipologia</th><td>{html.escape(str(info_row.dssubunidade or '—'))}</td></tr>
      <tr><th>Setor fiscal</th><td>{html.escape(str(info_row.cdsetorfiscal or '—'))}</td>
          <th>Area privativa</th><td>{fmt_num(info_row.vlareausopriv, 1)} m2</td></tr>
      <tr><th>Andar</th><td>{fmt_int(info_row.nupavimentounidade)} de {fmt_int(info_row.nupavimentos)}</td>
          <th>IPTU</th><td>{fmt_rs(info_row.vliptu)}</td></tr>
    </table>
    {bloco_end}
    <h2>Comparacao Venal x Mercado</h2>
    <div class="cards">
      <div class="card"><div class="rotulo">Valor venal (prefeitura)</div><div class="valor">{fmt_rs(vvenal)}</div></div>
      <div class="card destaque"><div class="rotulo">Estimativa de mercado (LightGBM)</div><div class="valor">{fmt_rs(prev)}</div>
        <div class="sub">IC 80%: {fmt_rs(pred['ic_inf'])} a {fmt_rs(pred['ic_sup'])}</div></div>
      <div class="card"><div class="rotulo">Segunda opiniao (hedonica)</div><div class="valor">{fmt_rs(pred['previsto_hedonico'])}</div></div>
      <div class="card"><div class="rotulo">Diferenca venal vs mercado</div><div class="valor">{dif_html}</div></div>
    </div>
    <p>Classificacao: <span class="pilha" style="background:{badge_cor}">{badge_txt}</span></p>
    <p class="metodologia">Avaliacao baseada em caracteristicas cadastrais (sem transmissao registrada).
    Modelo com idade ({html.escape(versao)}), apenas Apartamento. Sem uso de dados de anuncios.</p>
    {_mem_html(pred["memoria"])}
    {_tabela_comparaveis(comps)}
    {mapa_html(lat, lon, comps) if np.isfinite(lat) else ""}
    <p class="nota">A classificacao e subsidio tecnico — a decisao e do auditor fiscal.<br>
    <strong>Metodologia de correcao monetaria dos comparaveis:</strong> valores atualizados pelo IPCA/IBGE (serie 433, SGS/BCB).</p>
    """
