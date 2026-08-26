# -*- coding: utf-8 -*-
"""
Versao SOMENTE APARTAMENTOS da avaliacao de status (pedido do usuario,
17/07/2026): mesma regra de gerar_status_avaliacao_raw.py — comparacao unica
com o VALOR DA TRANSACAO ATUALIZADO (IPCA), ajuste por fracao transmitida,
tolerancia +/-15% (meta COD <= 15%, IAAO/NBR 14653-2) e "suspeito" fora de
0,5-2,0 — aplicada apenas as linhas de Apartamento da planilha bruta.

Mantem as abas da planilha de status original ("Exportar Planilha", "SQL",
"Indicadores IAAO (Modelo)") e insere AO FINAL das colunas originais:
  FRACAO_TRANSMITIDA | VALOR DA TRANSACAO ATUALIZADO (IPCA) |
  ESTIMATIVA DO MODELO (LIGHTGBM) | VALOR DA OPINIAO HEDONICA |
  STATUS DA AVALIACAO | JUSTIFICATIVA

Executar:  python gerar_status_avaliacao_apartamentos.py
Gera:      ITIV/Informações ITIV 20260610 - Status Apartamentos.xlsx
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xlsxwriter

_T0 = time.time()


def _log(msg: str) -> None:
    print(f"[{time.time()-_T0:7.1f}s] {msg}", flush=True)


PASTA_CODIGO = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_CODIGO))
from metricas_iaao_por_decil import metricas_razao, prb_global

RAIZ = Path(__file__).resolve().parent.parent.parent  # .../ITIV
PASTA_MODELO = RAIZ / "Modelo_Apartamentos_Aprovado"
PASTA_APP_ANTIGO = RAIZ / "entrega_equipe_20260615"
ARQUIVO_ENTRADA = RAIZ / "Informações ITIV 20260610.xlsx"
ARQUIVO_LOTE = PASTA_MODELO / "Avaliacao_Lote_Apartamentos_ITIV.xlsx"
ARQUIVO_SAIDA = RAIZ / "Informações ITIV 20260610 - Status Apartamentos.xlsx"

sys.path.insert(0, str(PASTA_APP_ANTIGO))
from src import config as cfg
from src.limpeza import baixar_serie_ipca, deflacionar_ipca

from gerar_status_avaliacao_raw import (  # reusa as regras ja decididas
    TOLERANCIA, COMPATIVEL, COMPATIVEL_ABAIXO, NECESSITA_AUDITOR, SUSPEITO,
    FORA_ESCOPO, classificar, fracao_transmitida,
)

COLS_FINAIS = [
    "FRACAO_TRANSMITIDA",
    "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)",
    "ESTIMATIVA DO MODELO (LIGHTGBM)",
    "VALOR DA OPINIAO HEDONICA",
    "STATUS DA AVALIAÇÃO",
    "JUSTIFICATIVA",
]


def main() -> None:
    _log(f"Carregando {ARQUIVO_ENTRADA.name} (~1 min)...")
    df = pd.read_excel(ARQUIVO_ENTRADA, sheet_name="Exportar Planilha", engine="calamine")
    sql_df = pd.read_excel(ARQUIVO_ENTRADA, sheet_name="SQL", engine="calamine", header=None)
    _log(f"  {len(df):,} transações carregadas (todas as tipologias).")

    df = df[df[cfg.COL_TIPOLOGIA] == "Apartamento"].reset_index(drop=True)
    _log(f"  {len(df):,} transações de Apartamento (escopo desta planilha).")

    _log("Carregando estimativas do modelo (lote já calculado)...")
    lote = pd.read_excel(ARQUIVO_LOTE, engine="calamine")
    lote_idx = lote.drop_duplicates("SQTRANSMISSAO").set_index("SQTRANSMISSAO")

    est = df["SQTRANSMISSAO"].map(lote_idx["ESTIMATIVA DO MODELO (LIGHTGBM)"])
    hed = df["SQTRANSMISSAO"].map(lote_idx["VALOR DA OPINIAO HEDONICA"])

    _log("Ajustando estimativas por fração transmitida...")
    frac = pd.Series(
        [fracao_transmitida(ft, fc)
         for ft, fc in zip(df["VLFRACAOTERRENO"], df["VLFRACAOCONSTRUCAO"])],
        index=df.index,
    )
    n_frac = int((frac < 1.0).sum())
    _log(f"  {n_frac:,} transações com fração < 100% — estimativas multiplicadas pela fração.")
    est = est * frac
    hed = hed * frac

    _log("Recalculando o valor da transação atualizado (IPCA, mesma fórmula do treino)...")
    ipca = baixar_serie_ipca()
    valida = (
        pd.to_numeric(df[cfg.COL_VALOR_TRANSACAO], errors="coerce").fillna(0) > 0
    ) & pd.to_datetime(df[cfg.COL_DATA], errors="coerce").notna()
    _log(f"  {valida.sum():,} / {len(df):,} linhas com valor declarado > 0 e data válida.")
    sub_defl = deflacionar_ipca(df.loc[valida, [cfg.COL_VALOR_TRANSACAO, cfg.COL_DATA]], ipca)
    valor_atualizado = pd.Series(np.nan, index=df.index)
    valor_atualizado.loc[valida] = sub_defl[cfg.COL_VALOR_DEFL].to_numpy()

    _log("Classificando...")
    resultados = [classificar(v, e) for v, e in zip(valor_atualizado, est)]

    # insere as colunas novas AO FINAL, na ordem pedida
    df["FRACAO_TRANSMITIDA"] = frac
    df["VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"] = valor_atualizado
    df["ESTIMATIVA DO MODELO (LIGHTGBM)"] = est
    df["VALOR DA OPINIAO HEDONICA"] = hed
    df["STATUS DA AVALIAÇÃO"] = [r[0] for r in resultados]
    df["JUSTIFICATIVA"] = [r[1] for r in resultados]

    contagem = df["STATUS DA AVALIAÇÃO"].value_counts()
    _log("Distribuição: " + str(dict(contagem)))

    # --- indicadores IAAO (só Compra e Venda; exclui "Suspeito") -----------
    df["_ANO"] = pd.to_datetime(df[cfg.COL_DATA], errors="coerce").dt.year
    base_m = (
        df["DSTIPOTRANSACAO"].astype(str).str.startswith("Compra e Venda")
        & df["ESTIMATIVA DO MODELO (LIGHTGBM)"].notna()
        & (df["ESTIMATIVA DO MODELO (LIGHTGBM)"] > 0)
        & (df["VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"] > 0)
        & (df["STATUS DA AVALIAÇÃO"] != SUSPEITO)
    )

    def calc(m):
        av = df.loc[m, "ESTIMATIVA DO MODELO (LIGHTGBM)"].to_numpy(float)
        sp = df.loc[m, "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"].to_numpy(float)
        return metricas_razao(av, sp), prb_global(av, sp)

    linhas_ind = []
    anos = sorted(a for a in df.loc[base_m, "_ANO"].dropna().unique() if a >= 2021)
    for ano in anos:
        met, prb = calc(base_m & (df["_ANO"] == ano))
        linhas_ind.append((str(int(ano)), met, prb))
    met_ate_2020 = base_m & (df["_ANO"] < 2021)
    if met_ate_2020.any():
        met, prb = calc(met_ate_2020)
        linhas_ind.insert(0, ("Até 2020", met, prb))
    met_total, prb_total = calc(base_m)
    linhas_ind.append(("Total", met_total, prb_total))

    print("\nIndicadores IAAO (Apartamentos, Compra e Venda, sem 'Suspeito'):")
    for nome, met, prb in linhas_ind:
        print(f"  {nome:>8}: n={met['n']:>7,}  razão mediana={met['razao_mediana']:.3f}  "
              f"COD(mediano)={met['COD_mediano']:.1f}%  PRD={met['PRD']:.3f}  PRB={prb:.3f}")

    df = df.drop(columns=["_ANO"])

    # --- gravação -----------------------------------------------------------
    _log(f"Gravando {ARQUIVO_SAIDA.name}...")
    wb = xlsxwriter.Workbook(str(ARQUIVO_SAIDA), {"constant_memory": True,
                                                  "default_date_format": "dd/mm/yyyy"})
    ws = wb.add_worksheet("Exportar Planilha")

    n_linhas, n_cols = df.shape
    col_status = df.columns.get_loc("STATUS DA AVALIAÇÃO")
    col_just = df.columns.get_loc("JUSTIFICATIVA")

    cab_fmt = wb.add_format({"bold": True, "bg_color": "#1A3A5C", "font_color": "white"})
    for c, nome_col in enumerate(df.columns):
        ws.write(0, c, nome_col, cab_fmt)
    ws.autofilter(0, 0, n_linhas, n_cols - 1)
    ws.freeze_panes(1, 0)
    ws.set_column(col_status, col_status, 55)
    ws.set_column(col_just, col_just, 70)

    fmt_status = {
        COMPATIVEL: wb.add_format({"bg_color": "#C6EFCE"}),
        COMPATIVEL_ABAIXO: wb.add_format({"bg_color": "#DDEBF7"}),
        NECESSITA_AUDITOR: wb.add_format({"bg_color": "#FFC7CE"}),
        SUSPEITO: wb.add_format({"bg_color": "#FFEB9C"}),
        FORA_ESCOPO: wb.add_format({"bg_color": "#F2F2F2"}),
    }

    valores = df.to_numpy(dtype=object)
    status_vals = df["STATUS DA AVALIAÇÃO"].to_numpy()
    for i in range(n_linhas):
        linha = valores[i]
        r = i + 1
        for c in range(n_cols):
            v = linha[c]
            if v is None:
                continue
            try:
                if pd.isna(v):
                    continue
            except (TypeError, ValueError):
                pass
            if c == col_status:
                ws.write(r, c, v, fmt_status[status_vals[i]])
            elif isinstance(v, pd.Timestamp):
                ws.write_datetime(r, c, v.to_pydatetime())
            else:
                ws.write(r, c, v)
        if i % 20000 == 0 and i > 0:
            _log(f"  ... {i:,} linhas gravadas")

    _log("Gravando aba SQL...")
    ws_sql = wb.add_worksheet("SQL")
    for i, row in sql_df.iterrows():
        v = row[0]
        if pd.isna(v):
            continue
        ws_sql.write_string(i, 0, str(v))

    # --- aba de indicadores IAAO -------------------------------------------
    ws_ind = wb.add_worksheet("Indicadores IAAO (Modelo)")
    azul = wb.add_format({"bold": True, "font_size": 13, "font_color": "#1A3A5C"})
    nota_fmt = wb.add_format({"italic": True, "font_size": 9, "font_color": "#666666"})
    cab_ind = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1A3A5C",
                             "align": "center"})
    wrap_fmt = wb.add_format({"text_wrap": True, "valign": "top"})
    bold_fmt = wb.add_format({"bold": True, "font_color": "#1A3A5C"})

    ws_ind.set_column(0, 0, 100)
    ws_ind.write(0, 0, "Indicadores IAAO — Estimativa do modelo (LightGBM) x Valor da "
                       "Transação Atualizado (IPCA) — SOMENTE APARTAMENTOS", azul)
    ws_ind.write(1, 0, "Restrito a transações de 'Compra e Venda' (qualquer subtipo); exclui as "
                       "classificadas como 'Suspeito' (prováveis erros de dado). Valor da transação "
                       "atualizado = VLTRANSACAO corrigido pelo IPCA (série 433, BCB), mesma fórmula "
                       "do pipeline de treino do modelo.", nota_fmt)

    cabecalho = ["Recorte", "n", "Razão mediana", "COD (média, %)", "COD (mediano, %)",
                 "PRD", "PRB", "Meta IAAO"]
    for c, texto in enumerate(cabecalho):
        ws_ind.write(3, c, texto, cab_ind)

    meta_combinada = "Razão 0,98–1,03 | COD ≤15% | PRD 0,98–1,03 | PRB -0,05–0,05"
    for i, (nome, met, prb) in enumerate(linhas_ind):
        r = 4 + i
        ultimo = i == len(linhas_ind) - 1
        vals = [nome, met["n"], round(met["razao_mediana"], 3), round(met["COD"], 1),
                round(met["COD_mediano"], 1), round(met["PRD"], 3), round(prb, 3), meta_combinada]
        for c, v in enumerate(vals):
            ws_ind.write(r, c, v, bold_fmt if ultimo and c == 0 else None)

    for c, largura in enumerate([100, 8, 14, 16, 18, 8, 8, 50]):
        if c > 0:
            ws_ind.set_column(c, c, largura)

    linha_nota = 4 + len(linhas_ind) + 1
    ws_ind.write(linha_nota, 0, "O COD (média) é sensível a casos extremos remanescentes; use o "
                                "COD (mediano) como referência mais robusta.", nota_fmt)

    ws_ind.write(linha_nota + 2, 0, "O que significam esses indicadores (em palavras simples)", azul)
    explicacoes = [
        ("COD — Coeficiente de Dispersão",
         "Mede o quanto as avaliações do modelo variam de um imóvel para outro, para mais ou para "
         "menos, em relação ao valor típico. Quanto MENOR o COD, mais consistente é o modelo. "
         "A referência aceita para imóveis residenciais é até 15%."),
        ("PRD — Price-Related Differential",
         "Verifica se o modelo trata melhor os imóveis baratos do que os caros, ou vice-versa. "
         "O valor ideal é próximo de 1,0 (entre 0,98 e 1,03)."),
        ("PRB — Price-Related Bias",
         "Mede a mesma ideia do PRD, mas de forma estatisticamente mais robusta. Ideal entre "
         "-0,05 e +0,05: perto de zero significa que não há favorecimento por faixa de preço."),
        ("Razão mediana",
         "Compara, no meio da distribuição, quanto o modelo estima em relação ao valor da transação "
         "atualizado. 1,0 = acerto em cheio na mediana; acima de 1,0 = modelo tende a estimar mais "
         "alto; abaixo = mais baixo."),
    ]
    r = linha_nota + 3
    for nome_ind, texto in explicacoes:
        ws_ind.write(r, 0, nome_ind, bold_fmt)
        r += 1
        ws_ind.write(r, 0, texto, wrap_fmt)
        ws_ind.set_row(r, 48)
        r += 2

    wb.close()
    _log(f"Pronto: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
