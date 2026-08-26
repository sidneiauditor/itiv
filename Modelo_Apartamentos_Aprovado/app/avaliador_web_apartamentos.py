# -*- coding: utf-8 -*-
"""
Avaliador ITIV — Apartamentos (produção com idade + inscrição relativa).

Modelo LightGBM promovido em 26/08/2026 (candidato idade_mais_rel), com
segunda opinião hedônica das Etapas 4/5. Escopo: apenas Apartamento com
compra e venda registrada. Nao usa dados de anuncios — so transacoes reais.

Executar:  python avaliador_web_apartamentos.py
Abrir:     http://localhost:8766
"""
from __future__ import annotations

import html
import json
import os
import pickle
import sys
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

GOOGLE_SV_KEY = os.environ.get("GOOGLE_SV_KEY", "AIzaSyC-RLhNZAAF5kAbLt5rm6q-vUj44xLyPz4")

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.neighbors import BallTree
from pyproj import Transformer as _Transformer

RAIZ = Path(__file__).resolve().parent.parent.parent  # .../ITIV
PASTA_MODELO = RAIZ / "Modelo_Apartamentos_Aprovado"
PASTA_APP_ANTIGO = RAIZ / "entrega_equipe_20260615"

sys.path.insert(0, str(PASTA_APP_ANTIGO))
sys.path.insert(0, str(PASTA_MODELO / "codigo"))

from src import config as cfg
from src.limpeza import carregar_ou_cachear_bruto, baixar_serie_ipca, deflacionar_ipca

import apartamentos_lib as aplib
from idade_features import FEATURES_IDADE, carregar_nascimento
from inscricao_relativa import FEATURES_REL, anexar_inscricao_relativa

PORTA = 8766
R_TERRA = 6_371_000
VERSAO_MODELO = "idade + inscrição relativa (promovido 26/08/2026)"

print("Carregando dados e o modelo de apartamentos com idade (uma vez, ~1 min)...", flush=True)

BRUTO = carregar_ou_cachear_bruto()
BRUTO[cfg.COL_ID] = BRUTO[cfg.COL_ID].astype(int)
BRUTO_APTO = BRUTO[BRUTO[cfg.COL_TIPOLOGIA] == "Apartamento"].copy()

# Serie IPCA para o fallback do valor declarado: a TABELA de modelagem so tem o
# declarado corrigido para as transacoes que passaram no pipeline (~19% da base);
# fora delas, o VLTRANSACAO bruto e atualizado aqui com a mesma formula.
_IPCA = baixar_serie_ipca()

# TABELA de modelagem: fornece declarado deflacionado, VVA, area_modelo e lat/lon
# ja calculados pelo pipeline (BRUTO nao tem essas colunas derivadas).
TABELA = pd.read_parquet(cfg.ARQUIVO_TABELA_MODELAGEM)
TABELA[cfg.COL_ID] = TABELA[cfg.COL_ID].astype(int)
TABELA[cfg.COL_DATA] = pd.to_datetime(TABELA[cfg.COL_DATA])
TABELA_APTO = TABELA[TABELA["TIPOLOGIA"] == "Apartamento"].copy() if "TIPOLOGIA" in TABELA.columns else TABELA.copy()

POOL = pd.read_parquet(PASTA_MODELO / "dados" / "amostras" / "pool_treino_parametros.parquet")
CATEGORIAS_SETOR = pd.Categorical(POOL["CDSETORFISCAL"]).categories
POOL["KNN_PROXY"] = aplib.calcular_knn_proxy(POOL, POOL, k=aplib.K_VIZINHOS)

_FEATURES_JSON = json.loads(
    (PASTA_MODELO / "dados" / "features_producao.json").read_text(encoding="utf-8")
)
FEATURES_PRODUCAO = list(_FEATURES_JSON["candidato"])
FILL_MEDIANAS = json.loads(
    (PASTA_MODELO / "dados" / "fill_medians_producao.json").read_text(encoding="utf-8")
)
IDADE_MEDIANA_TREINO = float(FILL_MEDIANAS.get("IDADE_NA_TRANSACAO_IMP", 13.0))

_NASC_CSV = PASTA_MODELO / "dados" / "Nascimento_Imovel.csv"
NASCIMENTO = carregar_nascimento(_NASC_CSV if _NASC_CSV.exists() else None)
NASCIMENTO_MAP = NASCIMENTO.set_index("CDINSCRICAOIMOB")["AACONSTRUCAO"].to_dict()

STATS_SETOR = pd.read_parquet(PASTA_MODELO / "dados" / "stats_setor_inscricao_treino.parquet")
with open(PASTA_MODELO / "dados" / "vals_inscricao_por_setor.pkl", "rb") as _fh:
    STATS_SETOR.attrs["vals_por_setor"] = pickle.load(_fh)

_MODELO_TXT = (PASTA_MODELO / "dados" / "modelo_lightgbm_apartamentos.txt").read_text(encoding="utf-8")
MODELO_LGBM = lgb.Booster(model_str=_MODELO_TXT)  # caminho com acento quebra o fopen (C++) do LightGBM no Windows
_, _, MEDIANA_PROXY = aplib.montar_X_y(POOL)
MODELO_HED, COLUNAS_HED = aplib.treinar_hedonico(POOL)

# IC 80%: holdout do candidato promovido (PRED_idade_mais_rel)
_PREV_PROM = PASTA_MODELO / "dados" / "amostras" / "teste_final_previsoes_promovido.parquet"
if _PREV_PROM.exists():
    TESTE_PREV = pd.read_parquet(_PREV_PROM)
    _col_pred = "PRED_idade_mais_rel"
else:
    TESTE_PREV = pd.read_parquet(PASTA_MODELO / "dados" / "amostras" / "teste_final_previsoes.parquet")
    _col_pred = "VALOR_PREVISTO_LGBM"
_RAZAO_LGBM = (TESTE_PREV["VLTRANSACAO_DEFLACIONADO"] / TESTE_PREV[_col_pred]).replace(
    [np.inf, -np.inf], np.nan).dropna()
IC80_INF, IC80_SUP = _RAZAO_LGBM.quantile([0.10, 0.90])

_UTM2GEO = _Transformer.from_crs(cfg.CRS_UTM, cfg.CRS_GEOGRAFICO, always_xy=True)

# --- Cadastro de imoveis (avaliacao sem transmissao) ---
_PLANILHA_CAD = RAIZ / "projeto_itiv" / "Imoveis Salvador.xlsx"
_PARQUET_CAD = _PLANILHA_CAD.with_suffix(".parquet")
try:
    print("Carregando cadastro de imoveis...", flush=True)
    if _PARQUET_CAD.exists():
        CADASTRO = pd.read_parquet(_PARQUET_CAD)
    else:
        CADASTRO = pd.read_excel(_PLANILHA_CAD, sheet_name="Exportar Planilha")
    CADASTRO["CDINSCRICAOIMOB"] = pd.to_numeric(CADASTRO["CDINSCRICAOIMOB"], errors="coerce")
    print(f"Cadastro carregado: {len(CADASTRO):,} imoveis.", flush=True)
except Exception as _e:  # noqa: BLE001
    print(f"Aviso: cadastro nao carregado ({_e})", flush=True)
    CADASTRO = pd.DataFrame()

print("Pronto. Abra http://localhost:%d" % PORTA, flush=True)


# ---------------------------------------------------------------------------
# Formatacao (identica ao app antigo)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Preparacao das features de producao (9 base + idade + inscricao relativa)
# ---------------------------------------------------------------------------

def _idade_na_transacao(inscricao, data_ref) -> tuple[float, int, int]:
    """Retorna (idade_imp, flag_ausente, flag_invalido) com mediana do treino."""
    insc = pd.to_numeric(inscricao, errors="coerce")
    ano_tx = pd.to_datetime(data_ref, errors="coerce")
    ano_tx = int(ano_tx.year) if pd.notna(ano_tx) else 2026
    if pd.isna(insc):
        return IDADE_MEDIANA_TREINO, 1, 0
    ano_const = NASCIMENTO_MAP.get(int(insc))
    if ano_const is None or (isinstance(ano_const, float) and np.isnan(ano_const)):
        return IDADE_MEDIANA_TREINO, 1, 0
    ano_const = float(ano_const)
    if not (1500 <= ano_const <= ano_tx):
        return IDADE_MEDIANA_TREINO, 0, 1
    idade = ano_tx - ano_const
    if idade < 0:
        return IDADE_MEDIANA_TREINO, 0, 1
    return float(idade), 0, 0


def _preparar_features(info: pd.Series, sq_para_var_tendencia: int | None) -> pd.DataFrame:
    """Monta o schema de producao a partir de uma linha bruta (BRUTO ou cadastro)."""
    area = pd.to_numeric(info.get(cfg.COL_AREA_PRIVATIVA), errors="coerce")
    if not (pd.notna(area) and area > 0):
        return pd.DataFrame()
    log_area = float(np.log(area))

    pav = pd.to_numeric(info.get(cfg.COL_PAVIMENTOS), errors="coerce")
    pav = pav if pd.notna(pav) and pav > 0 else np.nan

    andar = pd.to_numeric(info.get(cfg.COL_ANDAR), errors="coerce")
    flag_andar_ausente = int(pd.isna(andar) or andar <= 0)
    andar_unidade = float(andar) if pd.notna(andar) and andar > 0 else 0.0

    insc = pd.to_numeric(info.get(cfg.COL_INSCRICAO), errors="coerce")
    data_ref = info.get(cfg.COL_DATA)
    idade_imp, flag_ausente, flag_invalido = _idade_na_transacao(insc, data_ref)

    params = pd.DataFrame([{
        "LOG_AREA": log_area,
        "NUPAVIMENTOS": pav,
        "ANDAR_UNIDADE": andar_unidade,
        "FLAG_ANDAR_AUSENTE": flag_andar_ausente,
        "CDSETORFISCAL": info.get(cfg.COL_SETOR),
        "VLCOORDGEOX": pd.to_numeric(info.get(cfg.COL_COORD_X), errors="coerce"),
        "VLCOORDGEOY": pd.to_numeric(info.get(cfg.COL_COORD_Y), errors="coerce"),
        "CDINSCRICAOIMOB": insc,
        "IDADE_NA_TRANSACAO_IMP": idade_imp,
        "FLAG_ANO_AUSENTE": flag_ausente,
        "FLAG_ANO_INVALIDO": flag_invalido,
    }])

    if sq_para_var_tendencia is not None:
        achado = POOL[POOL["SQTRANSMISSAO"] == sq_para_var_tendencia]
        if achado.empty and "SQTRANSMISSAO" in TESTE_PREV.columns:
            achado = TESTE_PREV[TESTE_PREV["SQTRANSMISSAO"] == sq_para_var_tendencia]
        if not achado.empty and "VAR_TENDENCIA" in achado.columns:
            params["VAR_TENDENCIA"] = float(achado.iloc[0]["VAR_TENDENCIA"])
        else:
            params["VAR_TENDENCIA"] = float(FILL_MEDIANAS.get("VAR_TENDENCIA", 0.0))
    else:
        # avaliacao "hoje" (cadastro, sem transmissao): sem defasagem adicional
        params["VAR_TENDENCIA"] = 0.0

    params = anexar_inscricao_relativa(params, STATS_SETOR)
    return params


def _montar_X_producao(params: pd.DataFrame) -> pd.DataFrame:
    X = params[FEATURES_PRODUCAO].copy()
    X["CDSETORFISCAL"] = pd.Categorical(X["CDSETORFISCAL"], categories=CATEGORIAS_SETOR)
    for col, med in FILL_MEDIANAS.items():
        if col in X.columns:
            X[col] = X[col].fillna(med)
    if "KNN_PROXY" in X.columns:
        X["KNN_PROXY"] = X["KNN_PROXY"].fillna(MEDIANA_PROXY)
    return X


def _prever(params: pd.DataFrame) -> dict:
    """Roda LightGBM de producao + hedonica (segunda opiniao) sobre uma linha."""
    knn_proxy = aplib.calcular_knn_proxy(POOL, params, k=aplib.K_VIZINHOS)
    params = params.copy()
    params["KNN_PROXY"] = knn_proxy

    X = _montar_X_producao(params)
    log_pred = MODELO_LGBM.predict(X)[0]
    previsto_lgbm = float(np.exp(log_pred))
    ic_inf = previsto_lgbm * float(IC80_INF)
    ic_sup = previsto_lgbm * float(IC80_SUP)

    previsto_hed = float(np.exp(aplib.prever_hedonico(MODELO_HED, COLUNAS_HED, params)[0]))

    contrib = _memoria_calculo_lgbm(X.iloc[[0]], log_pred)

    return {
        "previsto_lgbm": previsto_lgbm,
        "previsto_hedonico": previsto_hed,
        "ic_inf": ic_inf,
        "ic_sup": ic_sup,
        "memoria": contrib,
        "features": params.iloc[0],
    }


def _memoria_calculo_lgbm(x_row: pd.DataFrame, log_pred: float) -> list[dict]:
    """Memoria de calculo via SHAP (contribuicao de cada parametro na previsao)."""
    try:
        import shap
        explainer = shap.TreeExplainer(MODELO_LGBM)
        shap_vals = explainer.shap_values(x_row)[0]
    except Exception:  # noqa: BLE001
        return []
    total_abs = np.sum(np.abs(shap_vals)) or 1.0
    linhas = []
    rotulos = {
        "LOG_AREA": "Area privativa", "NUPAVIMENTOS": "Pavimentos do predio",
        "ANDAR_UNIDADE": "Andar da unidade", "FLAG_ANDAR_AUSENTE": "Andar nao informado",
        "VAR_TENDENCIA": "Defasagem temporal", "VLCOORDGEOX": "Localizacao (X)",
        "VLCOORDGEOY": "Localizacao (Y)", "CDSETORFISCAL": "Setor fiscal",
        "KNN_PROXY": "Referencia de vizinhanca (R$/m2)",
        "IDADE_NA_TRANSACAO_IMP": "Idade do imovel (anos)",
        "FLAG_ANO_AUSENTE": "Ano de construcao ausente",
        "FLAG_ANO_INVALIDO": "Ano de construcao invalido",
        "LOG_INSCRICAO_REL": "Inscricao relativa no setor",
        "RANK_INSCRICAO_SETOR": "Posicao da inscricao no setor",
    }
    for col, sv in zip(x_row.columns, shap_vals):
        linhas.append({
            "parametro": rotulos.get(col, col),
            "contribuicao_pct": f"{sv / total_abs * 100:+.1f}%",
            "impacto": "aumenta o valor" if sv > 0 else "reduz o valor" if sv < 0 else "neutro",
        })
    linhas.sort(key=lambda c: abs(float(c["contribuicao_pct"].rstrip("%"))), reverse=True)
    return linhas


# ---------------------------------------------------------------------------
# Comparaveis e mapa (sem anuncios)
# ---------------------------------------------------------------------------

def comparaveis(lat: float, lon: float, data: pd.Timestamp, sq_excluir: int | None) -> list[dict]:
    """Os 15 apartamentos vizinhos mais proximos, vendidos ate 36 meses antes."""
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return []
    pool = TABELA_APTO[
        (TABELA_APTO[cfg.COL_DATA] < data.to_period("M").to_timestamp())
        & (TABELA_APTO[cfg.COL_DATA] >= data - pd.DateOffset(months=36))
        & TABELA_APTO[cfg.COL_LATITUDE].notna()
    ]
    if sq_excluir is not None:
        pool = pool[pool[cfg.COL_ID] != sq_excluir]
    if len(pool) < 3:
        return []
    tree = BallTree(np.radians(pool[[cfg.COL_LATITUDE, cfg.COL_LONGITUDE]].values), metric="haversine")
    k = min(15, len(pool))
    dist, idx = tree.query(np.radians([[lat, lon]]), k=k)
    out = []
    for d, i in zip(dist[0], idx[0]):
        v = pool.iloc[i]
        area = pd.to_numeric(v.get(cfg.COL_AREA_MODELO), errors="coerce")
        valor = pd.to_numeric(v.get(cfg.COL_VALOR_DEFL), errors="coerce")
        m2 = valor / area if area and area > 0 else np.nan
        out.append({
            "sq": int(v[cfg.COL_ID]), "data": fmt_data(v[cfg.COL_DATA]),
            "dist_m": round(d * R_TERRA), "area": round(float(area), 1) if np.isfinite(area) else 0,
            "valor": float(valor) if np.isfinite(valor) else 0.0,
            "m2": round(float(m2), 2) if np.isfinite(m2) else 0.0,
            "lat": round(float(v[cfg.COL_LATITUDE]), 5), "lon": round(float(v[cfg.COL_LONGITUDE]), 5),
        })
    return out


def mapa_html(lat: float, lon: float, comps: list[dict], titulo_id) -> str:
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return ""

    def sv_img(la: float, lo: float) -> str:
        return (f'<img src="/streetview?lat={la}&lon={lo}" '
                f'style="width:260px;height:130px;object-fit:cover;border-radius:4px;margin-top:6px;display:block">')

    popup_avaliado = f'<b>Imovel avaliado</b>' + sv_img(lat, lon)

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


# ---------------------------------------------------------------------------
# Avaliacao por transmissao (SQ / inscricao)
# ---------------------------------------------------------------------------

def avaliar_sq(sq: int) -> str:
    raw = BRUTO[BRUTO[cfg.COL_ID] == sq]
    if raw.empty:
        return f"<p class='erro'>SQ {sq} nao encontrado na base.</p>"
    info = raw.iloc[0]

    if str(info.get(cfg.COL_TIPOLOGIA, "")) != "Apartamento":
        return ("<p class='erro'>Este avaliador cobre apenas <b>Apartamento</b> com compra e venda "
                f"registrada. Tipologia encontrada: {html.escape(str(info.get(cfg.COL_TIPOLOGIA, '')))}.</p>")

    params = _preparar_features(info, sq_para_var_tendencia=sq)
    if params.empty:
        return "<p class='erro'>Transacao sem area privativa valida — nao ha como calcular o modelo.</p>"

    pred = _prever(params)

    tab = TABELA[TABELA[cfg.COL_ID] == sq]
    tab_row = tab.iloc[0] if not tab.empty else None

    lat = pd.to_numeric(tab_row.get(cfg.COL_LATITUDE), errors="coerce") if tab_row is not None else np.nan
    lon = pd.to_numeric(tab_row.get(cfg.COL_LONGITUDE), errors="coerce") if tab_row is not None else np.nan
    if not (np.isfinite(lat) and np.isfinite(lon)):
        # Transacao fora da tabela de modelagem: usa a coordenada UTM da base bruta
        x = pd.to_numeric(info.get(cfg.COL_COORD_X), errors="coerce")
        y = pd.to_numeric(info.get(cfg.COL_COORD_Y), errors="coerce")
        if pd.notna(x) and pd.notna(y) and x != 0 and y != 0:
            lon_c, lat_c = _UTM2GEO.transform(float(x), float(y))
            if cfg.LAT_MIN <= lat_c <= cfg.LAT_MAX and cfg.LON_MIN <= lon_c <= cfg.LON_MAX:
                lat, lon = lat_c, lon_c
    data_transacao = pd.to_datetime(info.get(cfg.COL_DATA))

    declarado = pd.to_numeric(tab_row.get(cfg.COL_VALOR_DEFL), errors="coerce") if tab_row is not None else np.nan
    rotulo_declarado = "Declarado (corrigido)"
    if not (np.isfinite(declarado) and declarado > 0):
        vl_bruto = pd.to_numeric(info.get(cfg.COL_VALOR_TRANSACAO), errors="coerce")
        dt_bruto = pd.to_datetime(info.get(cfg.COL_DATA), errors="coerce")
        if pd.notna(vl_bruto) and vl_bruto > 0 and pd.notna(dt_bruto):
            _defl = deflacionar_ipca(
                pd.DataFrame({cfg.COL_VALOR_TRANSACAO: [vl_bruto], cfg.COL_DATA: [dt_bruto]}), _IPCA)
            declarado = float(pd.to_numeric(_defl[cfg.COL_VALOR_DEFL].iloc[0], errors="coerce"))
            rotulo_declarado = "Declarado (atualizado IPCA)"
    vva = pd.to_numeric(info.get(cfg.COL_VVA), errors="coerce")
    area_mod = pd.to_numeric(info.get(cfg.COL_AREA_PRIVATIVA), errors="coerce")
    m2_declarado = declarado / area_mod if np.isfinite(area_mod) and area_mod > 0 and declarado > 0 else np.nan

    comps = comparaveis(lat, lon, data_transacao, sq_excluir=sq)

    dif_pct = (pred["previsto_lgbm"] - declarado) / declarado * 100 if declarado and declarado > 0 else float("nan")

    mem = pred["memoria"]
    mem_html = ""
    if mem:
        linhas = "".join(
            f"<tr><td>{html.escape(m['parametro'])}</td>"
            f"<td style='text-align:right'>{m['contribuicao_pct']}</td><td>{m['impacto']}</td></tr>"
            for m in mem
        )
        mem_html = f"""
        <h3>Memoria de calculo (modelo LightGBM, SHAP)</h3>
        <table><tr><th>Parametro</th><th>Contribuicao</th><th>Impacto</th></tr>{linhas}</table>
        """

    comps_html = _tabela_comparaveis(comps)

    assunto = f"Avaliacao ITIV (idade+rel) - SQ {sq}"
    corpo_mail = (f"Avaliacao do imovel SQ {sq} (inscricao {info.get(cfg.COL_INSCRICAO, '')}): "
                  f"declarado {fmt_rs(declarado)}, estimativa do modelo {fmt_rs(pred['previsto_lgbm'])}.")
    mailto = f"mailto:?subject={quote(assunto)}&body={quote(corpo_mail)}"

    return f"""
    <div class="acoes">
      <button class="btn-pdf" onclick="document.title='Avaliacao_ITIV_SQ_{sq}'; window.print()">Salvar em PDF</button>
      <a class="btn-mail" href="{mailto}">Enviar por e-mail</a>
    </div>
    <h2>Imovel — SQ {sq}</h2>
    <table class="info">
      <tr><th>Inscricao</th><td>{html.escape(str(info.get(cfg.COL_INSCRICAO, '')))}</td>
          <th>Tipologia</th><td>Apartamento</td></tr>
      <tr><th>Setor fiscal</th><td>{fmt_int(info.get(cfg.COL_SETOR, ''))}</td>
          <th>Data</th><td>{fmt_data(info.get(cfg.COL_DATA))}</td></tr>
      <tr><th>Area privativa</th><td>{fmt_num(area_mod, 1)} m2</td>
          <th>Andar</th><td>{fmt_int(info.get(cfg.COL_ANDAR))} de {fmt_int(info.get(cfg.COL_PAVIMENTOS))}</td></tr>
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

    {mem_html}
    {comps_html}
    {mapa_html(lat, lon, comps, sq)}

    <p class="nota">Escopo: Apartamento com compra e venda registrada (unico tipo coberto pelo modelo).
    Este avaliador NAO usa dados de anuncios — apenas transacoes reais (ITIV) entram no calculo e nos comparaveis.<br>
    Modelo: LightGBM com idade do imovel e inscricao relativa no setor ({VERSAO_MODELO});
    parametros base + idade + posicao cadastral no setor fiscal.
    IC 80% calculado sobre a distribuicao real de erro no holdout do candidato promovido.<br>
    A classificacao e subsidio tecnico — a decisao e do auditor fiscal.<br>
    <strong>Metodologia de correcao monetaria:</strong> valores atualizados pelo IPCA/IBGE (serie 433, SGS/BCB).</p>
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


def buscar(q: str) -> str:
    q = q.strip().replace(".", "").replace("-", "")
    if not q.isdigit():
        return "<p class='erro'>Digite um numero de SQ ou inscricao imobiliaria.</p>"
    n = int(q)
    if (BRUTO[cfg.COL_ID] == n).any():
        return avaliar_sq(n)
    insc = pd.to_numeric(BRUTO[cfg.COL_INSCRICAO], errors="coerce")
    achados = BRUTO[insc == n]
    if achados.empty:
        return f"<p class='erro'>Nenhum SQ nem inscricao = {n}.</p>"
    if len(achados) == 1:
        return avaliar_sq(int(achados.iloc[0][cfg.COL_ID]))
    linhas = "".join(
        f"<tr><td><a href='/avaliar?q={int(r[cfg.COL_ID])}'>{int(r[cfg.COL_ID])}</a></td>"
        f"<td>{fmt_data(r[cfg.COL_DATA])}</td>"
        f"<td>{html.escape(str(r[cfg.COL_TIPOLOGIA]))}</td>"
        f"<td style='text-align:right'>{fmt_rs(r[cfg.COL_VALOR_TRANSACAO])}</td></tr>"
        for _, r in achados.sort_values(cfg.COL_DATA, ascending=False).iterrows()
    )
    return f"""<h2>Inscricao {n}: {len(achados)} transmissoes — escolha uma</h2>
    <table><tr><th>SQ</th><th>Data</th><th>Tipologia</th><th>Valor declarado</th></tr>{linhas}</table>"""


# ---------------------------------------------------------------------------
# Avaliacao por cadastro (sem transmissao)
# ---------------------------------------------------------------------------

def _montar_row_cadastro(info: pd.Series) -> pd.Series:
    row = pd.Series({
        cfg.COL_ID: -int(info["CDINSCRICAOIMOB"]),
        cfg.COL_INSCRICAO: int(info["CDINSCRICAOIMOB"]),
        cfg.COL_TIPOLOGIA: str(info.get("DSSUBUNIDADE", "")),
        cfg.COL_AREA_PRIVATIVA: pd.to_numeric(info.get("VLAREAUSOPRIV"), errors="coerce"),
        cfg.COL_ANDAR: pd.to_numeric(info.get("NUPAVIMENTOUNIDADE"), errors="coerce"),
        cfg.COL_PAVIMENTOS: pd.to_numeric(info.get("NUPAVIMENTOS"), errors="coerce"),
        cfg.COL_SETOR: info.get("CDSETORFISCAL"),
        cfg.COL_COORD_X: pd.to_numeric(info.get("VLCOORDGEOX"), errors="coerce"),
        cfg.COL_COORD_Y: pd.to_numeric(info.get("VLCOORDGEOY"), errors="coerce"),
        cfg.COL_DATA: pd.Timestamp.today().normalize(),
    })
    return row


def avaliar_cadastro(inscricao: int) -> str:
    if CADASTRO.empty:
        return "<p class='erro'>Cadastro de imoveis nao carregado.</p>"
    achados = CADASTRO[CADASTRO["CDINSCRICAOIMOB"] == inscricao]
    if achados.empty:
        return f"<p class='erro'>Inscricao {inscricao} nao encontrada no cadastro.</p>"
    info = achados.iloc[0]

    if "apartamento" not in str(info.get("DSSUBUNIDADE", "")).lower():
        return ("<p class='erro'>Este avaliador cobre apenas <b>Apartamento</b>. "
                f"Tipologia no cadastro: {html.escape(str(info.get('DSSUBUNIDADE', '')))}.</p>")

    row = _montar_row_cadastro(info)
    params = _preparar_features(row, sq_para_var_tendencia=None)
    if params.empty:
        return "<p class='erro'>Imovel sem area privativa valida no cadastro.</p>"

    pred = _prever(params)

    x = pd.to_numeric(info.get("VLCOORDGEOX"), errors="coerce")
    y = pd.to_numeric(info.get("VLCOORDGEOY"), errors="coerce")
    lat = lon = np.nan
    if pd.notna(x) and pd.notna(y) and x != 0 and y != 0:
        lon_c, lat_c = _UTM2GEO.transform(float(x), float(y))
        if cfg.LAT_MIN <= lat_c <= cfg.LAT_MAX and cfg.LON_MIN <= lon_c <= cfg.LON_MAX:
            lat, lon = lat_c, lon_c

    vvenal = pd.to_numeric(info.get("VLVENALCADASTRO"), errors="coerce")
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

    comps = comparaveis(lat, lon, pd.Timestamp.today(), sq_excluir=None) if np.isfinite(lat) else []
    comps_html = _tabela_comparaveis(comps)

    mem = pred["memoria"]
    mem_html = ""
    if mem:
        linhas = "".join(
            f"<tr><td>{html.escape(m['parametro'])}</td>"
            f"<td style='text-align:right'>{m['contribuicao_pct']}</td><td>{m['impacto']}</td></tr>"
            for m in mem
        )
        mem_html = f"""<h3>Memoria de calculo (modelo LightGBM, SHAP)</h3>
        <table><tr><th>Parametro</th><th>Contribuicao</th><th>Impacto</th></tr>{linhas}</table>"""

    bloco_end = _bloco_endereco(lat, lon)
    if not bloco_end:
        dslogr = str(info.get("DSLOGRADOURO", ""))
        nuporta = str(info.get("NUPORTA", ""))
        cep = str(info.get("CDCEP", ""))
        end_txt = f"{dslogr}, {nuporta} — CEP {cep}".strip(", ")
        bloco_end = f"<h2>Localizacao</h2><div style='background:white;border:1px solid #ddd;border-radius:8px;padding:14px 18px'><b>{html.escape(end_txt)}</b></div>"

    assunto = f"Avaliacao Cadastral ITIV (idade+rel) - Inscricao {inscricao}"
    corpo_mail = (f"Avaliacao do imovel inscricao {inscricao} (sem transmissao): "
                  f"valor venal {fmt_rs(vvenal)}, estimativa do modelo {fmt_rs(prev)}, situacao {badge_txt}.")
    mailto = f"mailto:?subject={quote(assunto)}&body={quote(corpo_mail)}"

    return f"""
    <div class="acoes">
      <button class="btn-pdf" onclick="document.title='Avaliacao_Cadastral_{inscricao}'; window.print()">Salvar em PDF</button>
      <a class="btn-mail" href="{mailto}">Enviar por e-mail</a>
    </div>
    <h2>Imovel — Inscricao {inscricao} <small style="font-size:0.6em;color:#888">(cadastro — sem transmissao registrada)</small></h2>
    <table class="info">
      <tr><th>Inscricao</th><td>{inscricao}</td><th>Tipologia</th><td>{html.escape(str(info.get('DSSUBUNIDADE','—')))}</td></tr>
      <tr><th>Setor fiscal</th><td>{html.escape(str(info.get('CDSETORFISCAL','—')))}</td>
          <th>Area privativa</th><td>{fmt_num(info.get('VLAREAUSOPRIV'), 1)} m2</td></tr>
      <tr><th>Andar</th><td>{fmt_int(info.get('NUPAVIMENTOUNIDADE'))} de {fmt_int(info.get('NUPAVIMENTOS'))}</td>
          <th>IPTU</th><td>{fmt_rs(info.get('VLIPTU'))}</td></tr>
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
    Modelo com idade ({VERSAO_MODELO}), apenas Apartamento. Sem uso de dados de anuncios.</p>

    {mem_html}
    {comps_html}
    {mapa_html(lat, lon, comps, inscricao) if np.isfinite(lat) else ""}

    <p class="nota">A classificacao e subsidio tecnico — a decisao e do auditor fiscal.<br>
    <strong>Metodologia de correcao monetaria dos comparaveis:</strong> valores atualizados pelo IPCA/IBGE (serie 433, SGS/BCB).</p>
    """


# ---------------------------------------------------------------------------
# Servidor HTTP (identico em estrutura ao app antigo)
# ---------------------------------------------------------------------------

_CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f4f6f8; }
header { background: #1a3a5c; color: white; padding: 16px 32px; }
header h1 { margin: 0; font-size: 1.3em; }
main { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
.abas { display: flex; gap: 0; margin-bottom: 0; border-bottom: 2px solid #1a3a5c; }
.aba { padding: 10px 28px; font-size: 1em; background: #e8eef4; border: 1px solid #bbb;
  border-bottom: none; cursor: pointer; text-decoration: none; color: #333; border-radius: 6px 6px 0 0; }
.aba.ativa { background: #1a3a5c; color: white; font-weight: bold; }
.painel-busca { background: white; border: 1px solid #bbb; border-top: none;
  padding: 16px; border-radius: 0 0 8px 8px; margin-bottom: 24px; }
.painel-busca form { display: flex; gap: 8px; }
input[type=text] { flex: 1; padding: 12px; font-size: 1.1em; border: 1px solid #bbb; border-radius: 6px; }
button { padding: 12px 28px; font-size: 1.1em; background: #1a3a5c; color: white;
  border: 0; border-radius: 6px; cursor: pointer; }
table { border-collapse: collapse; width: 100%; background: white; font-size: 0.92em; margin: 8px 0 16px; }
th, td { border: 1px solid #ddd; padding: 7px 10px; text-align: left; }
th { background: #e8eef4; }
.info th { width: 130px; background: #f0f3f6; }
.cards { display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
.card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 14px 18px; min-width: 190px; }
.card.destaque { border: 2px solid #1a3a5c; }
.rotulo { color: #666; font-size: 0.85em; }
.valor { font-size: 1.35em; font-weight: bold; color: #1a3a5c; }
.sub { color: #888; font-size: 0.8em; margin-top: 4px; }
.pilha { color: white; padding: 4px 14px; border-radius: 12px; font-weight: bold; }
.erro { background: #ffebee; border-left: 4px solid #c62828; padding: 12px; }
.aviso { background: #fff8e1; border-left: 4px solid #ffa000; padding: 10px; }
.nota { color: #777; font-size: 0.85em; border-top: 1px solid #ddd; padding-top: 12px; margin-top: 24px; }
.metodologia { color: #666; font-size: 0.82em; font-style: italic; }
h2 { color: #1a3a5c; margin-top: 28px; }
h3 { color: #2c5f8a; }
.acoes { display: flex; gap: 10px; margin: 16px 0; }
.acoes button, .acoes a { padding: 10px 22px; font-size: 1em; border: 0; border-radius: 6px;
  cursor: pointer; text-decoration: none; display: inline-block; }
.btn-pdf { background: #2e7d32; color: white; }
.btn-mail { background: #1565c0; color: white; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  .acoes, .abas, .painel-busca, header, #mapa { display: none !important; }
  body { background: white; }
  main { max-width: 100%; margin: 0; }
  .card { break-inside: avoid; }
  table { font-size: 0.8em; }
  @page { margin: 1.5cm; }
}
"""

PAGINA = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>Avaliador ITIV — Apartamentos (idade + inscrição relativa)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>CSS_PLACEHOLDER</style></head><body>
<header><h1>Avaliador ITIV — Apartamentos (idade + inscrição relativa, 26/08/2026)</h1></header>
<main>
<div class="abas">
  <a class="aba {ativa_tx}" href="/avaliar">Transmissao (ITIV)</a>
  <a class="aba {ativa_cad}" href="/cadastro">Cadastro (Valor Venal)</a>
</div>
<div class="painel-busca">
<form action="{action}" method="get">
  <input type="text" name="q" placeholder="{placeholder}" value="{q}" autofocus>
  <button type="submit">Avaliar</button>
</form>
</div>
{conteudo}
</main></body></html>"""


def _streetview_bytes(lat: float, lon: float) -> bytes:
    params = f"size=260x130&location={lat},{lon}&fov=90&pitch=0&key={GOOGLE_SV_KEY}"
    sv_url = f"https://maps.googleapis.com/maps/api/streetview?{params}"
    with urllib.request.urlopen(sv_url, timeout=10) as r:
        return r.read()


def _geocode_reverso(lat: float, lon: float) -> dict:
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&language=pt-BR&key={GOOGLE_SV_KEY}"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read().decode())
    status = data.get("status", "")
    results = data.get("results", [])
    endereco = results[0].get("formatted_address", "") if results else ""
    return {"endereco": endereco, "status": status, "erro": data.get("error_message", "")}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        qs = parse_qs(url.query)

        if url.path == "/geocode":
            try:
                lat = float(qs["lat"][0])
                lon = float(qs["lon"][0])
                resultado = _geocode_reverso(lat, lon)
                corpo_geo = json.dumps(resultado, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo_geo)))
                self.send_header("Cache-Control", "public, max-age=86400" if resultado.get("endereco") else "no-store")
                self.end_headers()
                self.wfile.write(corpo_geo)
            except Exception:  # noqa: BLE001
                self.send_response(502)
                self.end_headers()
            return

        if url.path == "/streetview":
            try:
                lat = float(qs["lat"][0])
                lon = float(qs["lon"][0])
                img = _streetview_bytes(lat, lon)
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(img)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(img)
            except Exception:  # noqa: BLE001
                self.send_response(502)
                self.end_headers()
            return

        q = qs.get("q", [""])[0]

        if url.path == "/cadastro":
            if q:
                q_clean = q.strip().replace(".", "").replace("-", "")
                if q_clean.isdigit():
                    try:
                        conteudo = avaliar_cadastro(int(q_clean))
                    except Exception as e:  # noqa: BLE001
                        import traceback
                        conteudo = f"<p class='erro'>Erro: {html.escape(str(e))}</p><pre>{html.escape(traceback.format_exc()[-1500:])}</pre>"
                else:
                    conteudo = "<p class='erro'>Digite apenas numeros da inscricao imobiliaria.</p>"
            else:
                conteudo = "<p>Digite a inscricao imobiliaria (apartamento) para comparar o valor venal com o mercado.</p>"
            corpo = (PAGINA.format(
                q=html.escape(q), conteudo=conteudo, action="/cadastro", ativa_tx="", ativa_cad="ativa",
                placeholder="Digite a inscricao imobiliaria",
            ).replace("CSS_PLACEHOLDER", _CSS)).encode("utf-8")
        elif url.path == "/avaliar" and q:
            try:
                conteudo = buscar(q)
            except Exception as e:  # noqa: BLE001
                import traceback
                conteudo = f"<p class='erro'>Erro: {html.escape(str(e))}</p><pre>{html.escape(traceback.format_exc()[-1500:])}</pre>"
            corpo = (PAGINA.format(
                q=html.escape(q), conteudo=conteudo, action="/avaliar", ativa_tx="ativa", ativa_cad="",
                placeholder="Digite o SQ da transmissao ou a inscricao imobiliaria (apartamento)",
            ).replace("CSS_PLACEHOLDER", _CSS)).encode("utf-8")
        else:
            conteudo = "<p>Digite um SQ ou inscricao acima (apenas Apartamento). Modelo com idade + inscrição relativa (26/08/2026).</p>"
            corpo = (PAGINA.format(
                q=html.escape(q), conteudo=conteudo, action="/avaliar", ativa_tx="ativa", ativa_cad="",
                placeholder="Digite o SQ da transmissao ou a inscricao imobiliaria (apartamento)",
            ).replace("CSS_PLACEHOLDER", _CSS)).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, fmt, *args):  # silencia log por requisicao
        pass


def main() -> None:
    servidor = HTTPServer(("127.0.0.1", PORTA), Handler)
    webbrowser.open(f"http://localhost:{PORTA}")
    print(f"Avaliador (idade+rel) no ar em http://localhost:{PORTA} — Ctrl+C para encerrar.")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
