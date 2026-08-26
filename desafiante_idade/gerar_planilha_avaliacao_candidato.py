# -*- coding: utf-8 -*-
"""Gera planilha no mesmo espirito de 'Dados ITIV -Avaliação pelo Modelo.xlsx'
para o modelo candidato (idade + inscricao relativa), para encaminhar ao Selan.

Base: planilha ja encaminhada do modelo aprovado (mesmas colunas ITIV).
Acrescenta:
  ESTIMATIVA DO MODELO CANDIDATO (LIGHTGBM)
  STATUS DA AVALIACAO (CANDIDATO)
  JUSTIFICATIVA (CANDIDATO)

Apartamentos com area/features validas recebem estimativa do candidato;
demais linhas ficam Fora de Escopo no candidato (como no aprovado).

Saida:
  Modelo_Apartamentos_Candidato_Idade_20260811/
    Dados ITIV - Avaliacao pelo Modelo Candidato.xlsx
  e copia na raiz ITIV.

Executar:
  python -u desafiante_idade/gerar_planilha_avaliacao_candidato.py
"""
from __future__ import annotations

import pickle
import sys
import time
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import xlsxwriter

HERE = Path(__file__).resolve().parent
PASTA_ITIV = HERE.parent
PACOTE = PASTA_ITIV / "Modelo_Apartamentos_Candidato_Idade_20260811"
CODIGO_APROV = PASTA_ITIV / "Modelo_Apartamentos_Aprovado" / "codigo"
PASTA_APP = PASTA_ITIV / "entrega_equipe_20260615"

sys.path.insert(0, str(CODIGO_APROV))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PASTA_APP))

from idade_features import FEATURES_IDADE, anexar_idade, carregar_nascimento  # noqa: E402
from teste_inscricao_relativa_setor import (  # noqa: E402
    FEATURES_REL,
    anexar_inscricao_relativa,
)
from apartamentos_lib import (  # noqa: E402
    AMOSTRAS,
    FEATURES_LGBM,
    K_VIZINHOS,
    calcular_knn_proxy,
)
from metricas_iaao_por_decil import metricas_razao, prb_global  # noqa: E402

from src import config as cfg  # noqa: E402
from src.limpeza import baixar_serie_ipca, deflacionar_ipca  # noqa: E402

warnings.filterwarnings("ignore")

_T0 = time.time()


def _log(msg: str) -> None:
    print(f"[{time.time()-_T0:7.1f}s] {msg}", flush=True)


PLANILHA_APROVADA = next(PASTA_ITIV.glob("Dados ITIV*Aval*.xlsx"))
ARQUIVO_SAIDA_PACOTE = PACOTE / "Dados ITIV - Avaliacao pelo Modelo Candidato.xlsx"
ARQUIVO_SAIDA_RAIZ = PASTA_ITIV / "Dados ITIV - Avaliacao pelo Modelo Candidato.xlsx"

TOLERANCIA = 0.15
LIMITE_SUSPEITO_INF, LIMITE_SUSPEITO_SUP = 0.5, 2.0
COMPATIVEL = "Compatível"
COMPATIVEL_ABAIXO = "Compatível (valor da transação abaixo do valor estimado pelo modelo)"
NECESSITA_AUDITOR = "Necessidade Avaliação por Auditor"
SUSPEITO = "Valor da Transação Suspeito (fora de padrão)"
FORA_ESCOPO = "Fora de Escopo do Modelo"

FEATURES_CAND = list(FEATURES_LGBM) + FEATURES_IDADE + FEATURES_REL


def _fmt_rs(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def classificar(valor_atualizado, estimativa):
    if pd.isna(estimativa) or estimativa <= 0:
        return (FORA_ESCOPO,
                "Imóvel sem estimativa do modelo candidato (não é Apartamento com "
                "features válidas, ou fora do escopo).")
    if pd.isna(valor_atualizado) or valor_atualizado <= 0:
        return (FORA_ESCOPO,
                "Valor da transação atualizado ausente ou inválido — não é possível "
                "comparar com a estimativa do modelo candidato.")
    razao = estimativa / valor_atualizado
    dif = (razao - 1) * 100
    if razao < LIMITE_SUSPEITO_INF or razao > LIMITE_SUSPEITO_SUP:
        return (SUSPEITO,
                f"Estimativa do candidato ({_fmt_rs(estimativa)}) diverge {abs(dif):.0f}% "
                f"do valor atualizado ({_fmt_rs(valor_atualizado)}) — provável erro de dado.")
    if (1 - TOLERANCIA) <= razao <= (1 + TOLERANCIA):
        return (COMPATIVEL,
                f"Estimativa do candidato ({_fmt_rs(estimativa)}) está {abs(dif):.1f}% "
                f"{'acima' if dif >= 0 else 'abaixo'} do valor atualizado "
                f"({_fmt_rs(valor_atualizado)}) — dentro de ±{TOLERANCIA*100:.0f}%.")
    if razao < (1 - TOLERANCIA):
        return (COMPATIVEL_ABAIXO,
                f"Estimativa do candidato ({_fmt_rs(estimativa)}) está {abs(dif):.1f}% abaixo "
                f"do valor atualizado ({_fmt_rs(valor_atualizado)}) — sem risco de perda "
                f"de arrecadação.")
    return (NECESSITA_AUDITOR,
            f"Estimativa do candidato ({_fmt_rs(estimativa)}) está {dif:.1f}% acima do "
            f"valor atualizado ({_fmt_rs(valor_atualizado)}) — indício de subavaliação.")


def fracao_transmitida(ft, fc) -> float:
    ft = pd.to_numeric(ft, errors="coerce")
    fc = pd.to_numeric(fc, errors="coerce")
    f = ft if pd.notna(ft) and 0 < ft <= 1 else fc
    if pd.isna(f) or f <= 0 or f > 1:
        return 1.0
    return float(f)


def prever_candidato_apartamentos() -> pd.DataFrame:
    """Retorna DataFrame SQTRANSMISSAO + ESTIMATIVA_CANDIDATO para aptos com area."""
    _log("Carregando base bruta / tabela para scoring do candidato...")
    from src.limpeza import carregar_ou_cachear_bruto

    bruto = carregar_ou_cachear_bruto()
    bruto[cfg.COL_ID] = bruto[cfg.COL_ID].astype(int)
    apto = bruto[bruto[cfg.COL_TIPOLOGIA] == "Apartamento"].copy()
    _log(f"  Apartamentos na base: {len(apto):,}")

    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    pool["KNN_PROXY"] = calcular_knn_proxy(pool, pool, k=K_VIZINHOS)
    categorias_setor = pd.Categorical(pool["CDSETORFISCAL"]).categories

    nasc = carregar_nascimento(PACOTE / "dados" / "Nascimento_Imovel.csv")
    stats = pd.read_parquet(PACOTE / "dados" / "stats_setor_inscricao_treino.parquet")
    with open(PACOTE / "dados" / "vals_inscricao_por_setor.pkl", "rb") as fh:
        vals_map = pickle.load(fh)
    stats.attrs["vals_por_setor"] = vals_map
    fill = json_load_fill()

    modelo_txt = (PACOTE / "dados" / "modelo_lightgbm_candidato_idade_rel.txt").read_text(
        encoding="utf-8"
    )
    modelo = lgb.Booster(model_str=modelo_txt)

    area = pd.to_numeric(apto[cfg.COL_AREA_PRIVATIVA], errors="coerce")
    tem_area = area > 0
    apto = apto.loc[tem_area].copy()
    area = area.loc[tem_area]
    _log(f"  Com área privativa válida: {len(apto):,}")

    params = pd.DataFrame(index=apto.index)
    params["SQTRANSMISSAO"] = apto[cfg.COL_ID].astype(int).values
    params["CDINSCRICAOIMOB"] = pd.to_numeric(apto[cfg.COL_INSCRICAO], errors="coerce").values
    params["LOG_AREA"] = np.log(area.values)
    pav = pd.to_numeric(apto[cfg.COL_PAVIMENTOS], errors="coerce")
    params["NUPAVIMENTOS"] = pav.where(pav > 0).values
    andar = pd.to_numeric(apto[cfg.COL_ANDAR], errors="coerce")
    params["FLAG_ANDAR_AUSENTE"] = (andar.isna() | (andar <= 0)).astype(int).values
    params["ANDAR_UNIDADE"] = andar.where(andar > 0, 0).values
    params["CDSETORFISCAL"] = apto[cfg.COL_SETOR].values
    params["VLCOORDGEOX"] = pd.to_numeric(apto[cfg.COL_COORD_X], errors="coerce").values
    params["VLCOORDGEOY"] = pd.to_numeric(apto[cfg.COL_COORD_Y], errors="coerce").values

    # VAR_TENDENCIA: do pool/teste quando existir; senao 0
    teste_prev = pd.read_parquet(AMOSTRAS / "teste_final_previsoes.parquet")
    var_tend = pd.concat([
        pool[["SQTRANSMISSAO", "VAR_TENDENCIA"]],
        teste_prev[["SQTRANSMISSAO", "VAR_TENDENCIA"]],
    ]).drop_duplicates("SQTRANSMISSAO").set_index("SQTRANSMISSAO")["VAR_TENDENCIA"]
    params["VAR_TENDENCIA"] = params["SQTRANSMISSAO"].map(var_tend).fillna(0.0).values

    params["DATA_TRANSACAO"] = pd.to_datetime(apto[cfg.COL_DATA], errors="coerce").values
    params = anexar_idade(params, nasc, col_data="DATA_TRANSACAO")
    # reaplicar imputacao com mediana do treino (fill)
    med_idade = fill.get("IDADE_NA_TRANSACAO_IMP", params["IDADE_NA_TRANSACAO_IMP"].median())
    params["IDADE_NA_TRANSACAO_IMP"] = params["IDADE_NA_TRANSACAO"].fillna(med_idade)

    _log("  KNN_PROXY...")
    params["KNN_PROXY"] = calcular_knn_proxy(pool, params, k=K_VIZINHOS)

    params = anexar_inscricao_relativa(params, stats)

    X = params[FEATURES_CAND].copy()
    X["CDSETORFISCAL"] = pd.Categorical(X["CDSETORFISCAL"], categories=categorias_setor)
    for c, m in fill.items():
        if c in X.columns:
            X[c] = X[c].fillna(m)

    _log("  Prevendo candidato...")
    pred = np.exp(modelo.predict(X))

    # ajuste por fracao transmitida
    frac = np.array([
        fracao_transmitida(ft, fc)
        for ft, fc in zip(apto["VLFRACAOTERRENO"], apto["VLFRACAOCONSTRUCAO"])
    ])
    pred = pred * frac

    out = pd.DataFrame({
        "SQTRANSMISSAO": params["SQTRANSMISSAO"].astype(int).values,
        "ESTIMATIVA_CANDIDATO": pred,
    }).drop_duplicates("SQTRANSMISSAO", keep="last")
    _log(f"  Estimativas candidato: {len(out):,}")
    return out


def json_load_fill():
    import json
    p = PACOTE / "dados" / "fill_medians_candidato.json"
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    PACOTE.mkdir(parents=True, exist_ok=True)
    _log(f"Planilha aprovada de referência: {PLANILHA_APROVADA.name}")

    preds = prever_candidato_apartamentos()
    pred_map = preds.set_index("SQTRANSMISSAO")["ESTIMATIVA_CANDIDATO"]

    _log("Carregando planilha 'Dados ITIV - Avaliação pelo Modelo'...")
    df = pd.read_excel(PLANILHA_APROVADA, sheet_name="Exportar Planilha", engine="calamine", header=1)
    # limpa coluna vazia do meio, se houver
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
    _log(f"  {len(df):,} linhas | cols={list(df.columns)}")

    # renomeia colunas do aprovado para deixar claro na saida comparativa
    rename_aprov = {}
    for c in df.columns:
        cu = str(c).upper()
        if "ESTIMATIVA DO MODELO" in cu and "LIGHTGBM" in cu:
            rename_aprov[c] = "ESTIMATIVA MODELO APROVADO (LIGHTGBM)"
        elif "STATUS DA AVAL" in cu:
            rename_aprov[c] = "STATUS AVALIAÇÃO (APROVADO)"
        elif cu.strip() == "JUSTIFICATIVA":
            rename_aprov[c] = "JUSTIFICATIVA (APROVADO)"
    df = df.rename(columns=rename_aprov)

    # valor atualizado: usa coluna existente; se vazia, tenta recalcular
    col_tx = [c for c in df.columns if "TRANSA" in str(c).upper() and "ATUALIZ" in str(c).upper()]
    if not col_tx:
        raise RuntimeError("Coluna de valor atualizado não encontrada na planilha aprovada")
    col_valor = col_tx[0]

    df["ESTIMATIVA DO MODELO CANDIDATO (LIGHTGBM)"] = pd.to_numeric(
        df["SQTRANSMISSAO"], errors="coerce"
    ).map(pred_map)

    _log("Classificando status do candidato...")
    resultados = [
        classificar(v, e)
        for v, e in zip(
            pd.to_numeric(df[col_valor], errors="coerce"),
            df["ESTIMATIVA DO MODELO CANDIDATO (LIGHTGBM)"],
        )
    ]
    df["STATUS AVALIAÇÃO (CANDIDATO)"] = [r[0] for r in resultados]
    df["JUSTIFICATIVA (CANDIDATO)"] = [r[1] for r in resultados]

    cont = df["STATUS AVALIAÇÃO (CANDIDATO)"].value_counts()
    _log("Distribuição candidato: " + str(dict(cont)))

    # Indicadores IAAO — so compra e venda, exclui suspeito, so com estimativa candidato
    tipo = df.get("DSTIPOTRANSACAO", pd.Series(index=df.index, dtype=object)).astype(str)
    mask_iaao = (
        tipo.str.startswith("Compra e Venda")
        & df["ESTIMATIVA DO MODELO CANDIDATO (LIGHTGBM)"].notna()
        & (df["STATUS AVALIAÇÃO (CANDIDATO)"] != SUSPEITO)
        & (df["STATUS AVALIAÇÃO (CANDIDATO)"] != FORA_ESCOPO)
    )
    av = df.loc[mask_iaao, "ESTIMATIVA DO MODELO CANDIDATO (LIGHTGBM)"].to_numpy(float)
    sp = pd.to_numeric(df.loc[mask_iaao, col_valor], errors="coerce").to_numpy(float)
    ok = np.isfinite(av) & np.isfinite(sp) & (av > 0) & (sp > 0)
    met = metricas_razao(av[ok], sp[ok])
    prb = prb_global(av[ok], sp[ok])
    _log(
        f"IAAO candidato (Compra e Venda, sem suspeito): n={met['n']:,} "
        f"razão={met['razao_mediana']:.3f} COD={met['COD']:.1f}% "
        f"CODmed={met['COD_mediano']:.1f}% PRD={met['PRD']:.3f} PRB={prb:.3f}"
    )

    # Comparativo IAAO do aprovado na mesma mascara (quando houver estimativa aprovada)
    col_aprov_est = "ESTIMATIVA MODELO APROVADO (LIGHTGBM)"
    if col_aprov_est in df.columns:
        mask_ap = mask_iaao & df[col_aprov_est].notna()
        av_a = pd.to_numeric(df.loc[mask_ap, col_aprov_est], errors="coerce").to_numpy(float)
        sp_a = pd.to_numeric(df.loc[mask_ap, col_valor], errors="coerce").to_numpy(float)
        ok_a = np.isfinite(av_a) & np.isfinite(sp_a) & (av_a > 0) & (sp_a > 0)
        met_a = metricas_razao(av_a[ok_a], sp_a[ok_a])
        prb_a = prb_global(av_a[ok_a], sp_a[ok_a])
    else:
        met_a, prb_a = None, None

    _log("Gravando Excel (pode levar alguns minutos)...")
    for destino in (ARQUIVO_SAIDA_PACOTE, ARQUIVO_SAIDA_RAIZ):
        _gravar(df, destino, met, prb, met_a, prb_a, col_valor)
        _log(f"  OK: {destino}")

    _log("Concluído.")


def _gravar(df, caminho, met, prb, met_a, prb_a, col_valor):
    wb = xlsxwriter.Workbook(
        str(caminho),
        {"constant_memory": True, "default_date_format": "dd/mm/yyyy", "nan_inf_to_errors": True},
    )
    ws = wb.add_worksheet("Exportar Planilha")
    cab = wb.add_format({"bold": True, "bg_color": "#1A3A5C", "font_color": "white"})
    fmt_status = {
        COMPATIVEL: wb.add_format({"bg_color": "#C6EFCE"}),
        COMPATIVEL_ABAIXO: wb.add_format({"bg_color": "#DDEBF7"}),
        NECESSITA_AUDITOR: wb.add_format({"bg_color": "#FFC7CE"}),
        SUSPEITO: wb.add_format({"bg_color": "#FFEB9C"}),
        FORA_ESCOPO: wb.add_format({"bg_color": "#F2F2F2"}),
    }

    cols = list(df.columns)
    for c, nome in enumerate(cols):
        ws.write(0, c, nome, cab)
    ws.autofilter(0, 0, len(df), len(cols) - 1)
    ws.freeze_panes(1, 0)

    col_sc = cols.index("STATUS AVALIAÇÃO (CANDIDATO)")
    col_sa = cols.index("STATUS AVALIAÇÃO (APROVADO)") if "STATUS AVALIAÇÃO (APROVADO)" in cols else None
    ws.set_column(col_sc, col_sc, 55)
    if "JUSTIFICATIVA (CANDIDATO)" in cols:
        ws.set_column(cols.index("JUSTIFICATIVA (CANDIDATO)"), cols.index("JUSTIFICATIVA (CANDIDATO)"), 70)

    valores = df.to_numpy(dtype=object)
    status_c = df["STATUS AVALIAÇÃO (CANDIDATO)"].to_numpy()
    for i in range(len(df)):
        r = i + 1
        linha = valores[i]
        for c in range(len(cols)):
            v = linha[c]
            if v is None:
                continue
            try:
                if pd.isna(v):
                    continue
            except (TypeError, ValueError):
                pass
            if c == col_sc:
                ws.write(r, c, v, fmt_status.get(status_c[i]))
            elif col_sa is not None and c == col_sa:
                ws.write(r, c, v, fmt_status.get(str(v), None))
            elif isinstance(v, pd.Timestamp):
                ws.write_datetime(r, c, v.to_pydatetime())
            else:
                try:
                    ws.write(r, c, v)
                except TypeError:
                    ws.write(r, c, str(v))
        if i and i % 30000 == 0:
            _log(f"    ... {i:,} linhas")

    # Aba IAAO
    ws_ind = wb.add_worksheet("Indicadores IAAO (Modelo)")
    azul = wb.add_format({"bold": True, "font_size": 12, "font_color": "#1A3A5C"})
    nota = wb.add_format({"italic": True, "font_size": 9, "font_color": "#666666"})
    cab_ind = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1A3A5C"})
    ws_ind.set_column(0, 0, 55)
    ws_ind.write(0, 0, "Indicadores IAAO — Modelo CANDIDATO (idade + inscrição relativa)", azul)
    ws_ind.write(
        1, 0,
        "Comparação: estimativa do candidato × valor da transação atualizado (IPCA). "
        "Recorte: Compra e Venda; exclui Suspeito e Fora de Escopo. "
        "Pacote: Modelo_Apartamentos_Candidato_Idade_20260811. NÃO substitui o modelo aprovado.",
        nota,
    )
    headers = ["Modelo", "n", "Razão mediana", "COD (média %)", "COD (mediano %)", "PRD", "PRB", "Meta"]
    for c, h in enumerate(headers):
        ws_ind.write(3, c, h, cab_ind)
    meta = "Razão ~1 | COD ≤15% | PRD 0,98–1,03 | PRB ±0,05"
    ws_ind.write_row(4, 0, [
        "Candidato (idade+relativa)", met["n"], round(met["razao_mediana"], 3),
        round(met["COD"], 1), round(met["COD_mediano"], 1), round(met["PRD"], 3),
        round(prb, 3), meta,
    ])
    if met_a is not None:
        ws_ind.write_row(5, 0, [
            "Aprovado (mesma máscara, p/ referência)", met_a["n"], round(met_a["razao_mediana"], 3),
            round(met_a["COD"], 1), round(met_a["COD_mediano"], 1), round(met_a["PRD"], 3),
            round(prb_a, 3), meta,
        ])
    ws_ind.write(7, 0, "Decisão pendente do Selan: promover candidato ou manter aprovado.", nota)

    # Aba leia-me
    ws_l = wb.add_worksheet("LEIA-ME")
    ws_l.set_column(0, 0, 100)
    textos = [
        "PLANILHA PARA AVALIAÇÃO DO SELAN — MODELO CANDIDATO",
        "",
        "Esta planilha tem o mesmo espírito da 'Dados ITIV - Avaliação pelo Modelo.xlsx' "
        "encaminhada com o modelo aprovado em 14/07/2026.",
        "",
        "Colunas do ITIV (origem) + estimativa/status do MODELO APROVADO (já existentes) "
        "+ estimativa/status do MODELO CANDIDATO (idade + inscrição relativa no setor).",
        "",
        "O modelo candidato NÃO substitui o aprovado até decisão formal.",
        "Pasta do pacote: Modelo_Apartamentos_Candidato_Idade_20260811",
        "",
        "Como ler STATUS:",
        "  Compatível — diferença dentro de ±15%",
        "  Compatível (abaixo) — modelo abaixo do declarado, sem risco de arrecadação",
        "  Necessidade Avaliação por Auditor — modelo acima do declarado fora de ±15%",
        "  Suspeito — divergência >100% (provável erro de dado)",
        "  Fora de Escopo — sem estimativa (ex.: não apartamento / sem features)",
    ]
    for i, t in enumerate(textos):
        ws_l.write(i, 0, t, azul if i == 0 else None)

    wb.close()


if __name__ == "__main__":
    main()
