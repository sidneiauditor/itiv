# -*- coding: utf-8 -*-
"""
Avaliacao SOMENTE APARTAMENTOS sobre a planilha do SELAN
(ITIV_Base_Consolidada_2025_2026.xlsx, abas "Dados 2025" e "Dados 2026"),
pedido do usuario em 17/07/2026.

Regras identicas a gerar_status_avaliacao_raw.py (decisoes de 17/07/2026):
  - comparacao unica: VALOR DA TRANSACAO ATUALIZADO (IPCA) x estimativa LightGBM;
  - estimativa ajustada pela fracao transmitida (Fracao_Terreno/Fracao_Construcao
    da propria planilha do SELAN);
  - tolerancia +/-15% (meta COD <= 15%, IAAO/NBR 14653-2);
  - razao fora de 0,5-2,0 -> "Valor da Transacao Suspeito (fora de padrao)".

Mantem as abas originais do SELAN (Notas Metodologicas, Dados 2025, Dados 2026,
Resumo por Tipo 2025, Resumo por Tipo 2026) e acrescenta a aba
"Indicadores IAAO (Modelo)". Nas abas de dados ficam apenas as linhas de
Apartamento, com as colunas originais e, AO FINAL:
  FRACAO_TRANSMITIDA | VALOR DA TRANSACAO ATUALIZADO (IPCA) |
  ESTIMATIVA DO MODELO (LIGHTGBM) | VALOR DA OPINIAO HEDONICA |
  STATUS DA AVALIACAO | JUSTIFICATIVA

Executar:  python gerar_status_consolidada_apartamentos.py
Gera:      Modelo_Apartamentos_Aprovado/ITIV_Base_Consolidada_2025_2026 - Status Apartamentos.xlsx
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import openpyxl
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
ARQUIVO_SELAN = PASTA_APP_ANTIGO / "ITIV_Base_Consolidada_2025_2026.xlsx"
ARQUIVO_LOTE = PASTA_MODELO / "Avaliacao_Lote_Apartamentos_ITIV.xlsx"
ARQUIVO_SAIDA = PASTA_MODELO / "ITIV_Base_Consolidada_2025_2026 - Status Apartamentos.xlsx"

sys.path.insert(0, str(PASTA_APP_ANTIGO))
from src import config as cfg
from src.limpeza import baixar_serie_ipca, carregar_ou_cachear_bruto, deflacionar_ipca

from gerar_status_avaliacao_raw import (  # reusa as regras ja decididas
    COMPATIVEL, COMPATIVEL_ABAIXO, NECESSITA_AUDITOR, SUSPEITO, FORA_ESCOPO,
    classificar, fracao_transmitida,
)

COLUNAS_SELAN = [
    "Nosso_Numero", "Ano_Exercicio", "Tipo_Transacao", "Inscricao_Imobiliaria",
    "Adquirente", "Data_Liberacao", "Data_Pagamento", "VT", "VVA",
    "Fracao_Terreno", "Fracao_Construcao", "Valor_Pago_SAT", "Base_Inferida",
    "Qtd_Pagamentos_Consolidados", "Atipica",
]
COLS_NOVAS = [
    "FRACAO_TRANSMITIDA",
    "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)",
    "ESTIMATIVA DO MODELO (LIGHTGBM)",
    "VALOR DA OPINIAO HEDONICA",
    "STATUS DA AVALIAÇÃO",
    "JUSTIFICATIVA",
]


def processar_aba(nome_aba: str, xl: pd.ExcelFile, bruto_idx: pd.DataFrame,
                  lote_idx: pd.DataFrame, ipca) -> pd.DataFrame:
    df = xl.parse(nome_aba, header=2)
    df.columns = COLUNAS_SELAN
    df["Nosso_Numero"] = pd.to_numeric(df["Nosso_Numero"], errors="coerce")
    df = df.dropna(subset=["Nosso_Numero"]).copy()
    df["Nosso_Numero"] = df["Nosso_Numero"].astype(int)
    _log(f"  {nome_aba}: {len(df):,} guias na planilha do SELAN.")

    tipologia = df["Nosso_Numero"].map(bruto_idx[cfg.COL_TIPOLOGIA])
    df = df[tipologia == "Apartamento"].reset_index(drop=True)
    _log(f"  {nome_aba}: {len(df):,} guias de Apartamento (escopo).")

    frac = pd.Series(
        [fracao_transmitida(ft, fc)
         for ft, fc in zip(df["Fracao_Terreno"], df["Fracao_Construcao"])],
        index=df.index,
    )
    est = df["Nosso_Numero"].map(lote_idx["ESTIMATIVA DO MODELO (LIGHTGBM)"]) * frac
    hed = df["Nosso_Numero"].map(lote_idx["VALOR DA OPINIAO HEDONICA"]) * frac

    # valor da transacao atualizado: VT corrigido pelo IPCA, com a data da
    # transmissao (DTSOLICITACAO da base ITIV); sem ela, usa Data_Liberacao
    data = df["Nosso_Numero"].map(bruto_idx[cfg.COL_DATA])
    data = pd.to_datetime(data, errors="coerce").fillna(
        pd.to_datetime(df["Data_Liberacao"], errors="coerce"))
    vt = pd.to_numeric(df["VT"], errors="coerce")
    valida = (vt.fillna(0) > 0) & data.notna()
    valor_atualizado = pd.Series(np.nan, index=df.index)
    if valida.any():
        aux = pd.DataFrame({cfg.COL_VALOR_TRANSACAO: vt[valida], cfg.COL_DATA: data[valida]})
        valor_atualizado.loc[valida] = deflacionar_ipca(aux, ipca)[cfg.COL_VALOR_DEFL].to_numpy()

    resultados = [classificar(v, e) for v, e in zip(valor_atualizado, est)]
    df["FRACAO_TRANSMITIDA"] = frac
    df["VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"] = valor_atualizado
    df["ESTIMATIVA DO MODELO (LIGHTGBM)"] = est
    df["VALOR DA OPINIAO HEDONICA"] = hed
    df["STATUS DA AVALIAÇÃO"] = [r[0] for r in resultados]
    df["JUSTIFICATIVA"] = [r[1] for r in resultados]

    _log(f"  {nome_aba}: " + str(dict(df['STATUS DA AVALIAÇÃO'].value_counts())))
    return df


def indicadores(df: pd.DataFrame):
    m = (
        df["Tipo_Transacao"].astype(str).str.startswith("Compra e Venda")
        & df["ESTIMATIVA DO MODELO (LIGHTGBM)"].notna()
        & (df["ESTIMATIVA DO MODELO (LIGHTGBM)"] > 0)
        & (df["VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"] > 0)
        & (df["STATUS DA AVALIAÇÃO"] != SUSPEITO)
    )
    av = df.loc[m, "ESTIMATIVA DO MODELO (LIGHTGBM)"].to_numpy(float)
    sp = df.loc[m, "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"].to_numpy(float)
    return metricas_razao(av, sp), prb_global(av, sp)


def main() -> None:
    _log(f"Carregando {ARQUIVO_SELAN.name}...")
    xl = pd.ExcelFile(ARQUIVO_SELAN)

    _log("Carregando base ITIV (cache) e lote de estimativas...")
    bruto = carregar_ou_cachear_bruto()
    bruto[cfg.COL_ID] = bruto[cfg.COL_ID].astype(int)
    bruto_idx = bruto.drop_duplicates(cfg.COL_ID).set_index(cfg.COL_ID)
    lote = pd.read_excel(ARQUIVO_LOTE, engine="calamine")
    lote_idx = lote.drop_duplicates("SQTRANSMISSAO").set_index("SQTRANSMISSAO")
    ipca = baixar_serie_ipca()

    dados = {}
    for aba in ["Dados 2025", "Dados 2026"]:
        dados[aba] = processar_aba(aba, xl, bruto_idx, lote_idx, ipca)

    linhas_ind = []
    for aba, df in dados.items():
        met, prb = indicadores(df)
        linhas_ind.append((aba.replace("Dados ", ""), met, prb))
    total = pd.concat(dados.values(), ignore_index=True)
    met_t, prb_t = indicadores(total)
    linhas_ind.append(("Total (2025+2026)", met_t, prb_t))

    print("\nIndicadores IAAO (Apartamentos, Compra e Venda, sem 'Suspeito'):")
    for nome, met, prb in linhas_ind:
        print(f"  {nome:>17}: n={met['n']:>6,}  razão mediana={met['razao_mediana']:.3f}  "
              f"COD(mediano)={met['COD_mediano']:.1f}%  PRD={met['PRD']:.3f}  PRB={prb:.3f}")

    # --- originais para copia (notas e resumos) ----------------------------
    wb_orig = openpyxl.load_workbook(ARQUIVO_SELAN, read_only=True)

    _log(f"Gravando {ARQUIVO_SAIDA.name}...")
    wb = xlsxwriter.Workbook(str(ARQUIVO_SAIDA), {"default_date_format": "dd/mm/yyyy"})

    azul = wb.add_format({"bold": True, "font_size": 13, "font_color": "#1A3A5C"})
    cab_fmt = wb.add_format({"bold": True, "bg_color": "#1A3A5C", "font_color": "white"})
    nota_fmt = wb.add_format({"italic": True, "font_size": 9, "font_color": "#666666"})
    bold_fmt = wb.add_format({"bold": True, "font_color": "#1A3A5C"})
    wrap_fmt = wb.add_format({"text_wrap": True, "valign": "top"})
    fmt_rs = wb.add_format({"num_format": "R$ #,##0.00"})
    fmt_status = {
        COMPATIVEL: wb.add_format({"bg_color": "#C6EFCE"}),
        COMPATIVEL_ABAIXO: wb.add_format({"bg_color": "#DDEBF7"}),
        NECESSITA_AUDITOR: wb.add_format({"bg_color": "#FFC7CE"}),
        SUSPEITO: wb.add_format({"bg_color": "#FFEB9C"}),
        FORA_ESCOPO: wb.add_format({"bg_color": "#F2F2F2"}),
    }

    # --- aba Notas Metodologicas (copia + adendo) --------------------------
    ws_notas = wb.add_worksheet("Notas Metodológicas")
    ws_notas.set_column(0, 0, 120)
    r = 0
    for row in wb_orig["Notas Metodológicas"].iter_rows(values_only=True):
        v = next((x for x in row if x is not None), None)
        if v is not None:
            ws_notas.write(r, 0, str(v), wrap_fmt)
        r += 1
    r += 1
    ws_notas.write(r, 0, "ADENDO — AVALIAÇÃO PELO MODELO (VERSÃO SOMENTE APARTAMENTOS)", azul)
    adendo = [
        "Esta versão mantém apenas as guias de Apartamento (tipologia obtida na base ITIV pelo "
        "Nosso Número = SQTRANSMISSAO) e acrescenta, ao final das abas de dados, as colunas: "
        "FRACAO_TRANSMITIDA, VALOR DA TRANSAÇÃO ATUALIZADO (IPCA), ESTIMATIVA DO MODELO (LIGHTGBM), "
        "VALOR DA OPINIAO HEDONICA, STATUS DA AVALIAÇÃO e JUSTIFICATIVA.",
        "Comparação: sempre entre o valor da transação atualizado (VT corrigido pelo IPCA, série 433 "
        "do BCB, mesma fórmula do treino do modelo) e a estimativa do modelo LightGBM aprovado em "
        "14/07/2026, ajustada pela fração transmitida.",
        "Status possíveis: Compatível (±15%, meta normativa de COD ≤ 15%, IAAO/NBR 14653-2); "
        "Compatível (valor da transação abaixo do valor estimado) — sem risco de perda de arrecadação; "
        "Necessidade Avaliação por Auditor (modelo acima do valor, indício de subavaliação); "
        "Valor da Transação Suspeito (razão fora de 0,5–2,0 — provável erro de dado); "
        "Fora de Escopo do Modelo.",
        "As abas 'Resumo por Tipo' permanecem as originais do SELAN (todas as tipologias), para referência.",
    ]
    for texto in adendo:
        r += 1
        ws_notas.write(r, 0, texto, wrap_fmt)
        ws_notas.set_row(r, 44)

    # --- abas de dados ------------------------------------------------------
    titulos = {"Dados 2025": "ITIV — Base Consolidada — Janeiro a Maio — Apartamentos (2025)",
               "Dados 2026": "ITIV — Base Consolidada — Janeiro a Maio — Apartamentos (2026)"}
    todas_colunas = COLUNAS_SELAN + COLS_NOVAS
    col_vt = todas_colunas.index("VT")
    col_vva = todas_colunas.index("VVA")
    col_pago = todas_colunas.index("Valor_Pago_SAT")
    col_base = todas_colunas.index("Base_Inferida")
    col_atual = todas_colunas.index("VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)")
    col_est = todas_colunas.index("ESTIMATIVA DO MODELO (LIGHTGBM)")
    col_hed = todas_colunas.index("VALOR DA OPINIAO HEDONICA")
    col_status = todas_colunas.index("STATUS DA AVALIAÇÃO")
    col_just = todas_colunas.index("JUSTIFICATIVA")

    for aba, df in dados.items():
        ws = wb.add_worksheet(aba)
        ws.write(0, 0, titulos[aba], azul)
        for c, nome_col in enumerate(todas_colunas):
            ws.write(2, c, nome_col, cab_fmt)
        ws.autofilter(2, 0, 2 + len(df), len(todas_colunas) - 1)
        ws.freeze_panes(3, 0)
        for c in (col_vt, col_vva, col_pago, col_base, col_atual, col_est, col_hed):
            ws.set_column(c, c, 18, fmt_rs)
        ws.set_column(col_status, col_status, 55)
        ws.set_column(col_just, col_just, 70)

        status_vals = df["STATUS DA AVALIAÇÃO"].to_numpy()
        valores = df[todas_colunas].to_numpy(dtype=object)
        for i in range(len(df)):
            r = 3 + i
            for c in range(len(todas_colunas)):
                v = valores[i][c]
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

    # --- abas de resumo (copia dos valores originais) ----------------------
    for aba in ["Resumo por Tipo 2025", "Resumo por Tipo 2026"]:
        ws = wb.add_worksheet(aba)
        ws.set_column(0, 0, 45)
        ws.set_column(1, 3, 16)
        for r, row in enumerate(wb_orig[aba].iter_rows(values_only=True)):
            for c, v in enumerate(row):
                if v is None:
                    continue
                if r == 0 and c == 0:
                    ws.write(r, c, str(v), azul)
                elif r == 2:
                    ws.write(r, c, v, cab_fmt)
                else:
                    ws.write(r, c, v)

    # --- aba de indicadores -------------------------------------------------
    ws_ind = wb.add_worksheet("Indicadores IAAO (Modelo)")
    ws_ind.set_column(0, 0, 100)
    ws_ind.write(0, 0, "Indicadores IAAO — Estimativa do modelo (LightGBM) x Valor da Transação "
                       "Atualizado (IPCA) — SOMENTE APARTAMENTOS (planilha SELAN)", azul)
    ws_ind.write(1, 0, "Restrito a transações de 'Compra e Venda' (qualquer subtipo); exclui as "
                       "classificadas como 'Suspeito' (prováveis erros de dado).", nota_fmt)
    cabecalho = ["Recorte", "n", "Razão mediana", "COD (média, %)", "COD (mediano, %)",
                 "PRD", "PRB", "Meta IAAO"]
    cab_ind = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1A3A5C",
                             "align": "center"})
    for c, texto in enumerate(cabecalho):
        ws_ind.write(3, c, texto, cab_ind)
    meta = "Razão 0,98–1,03 | COD ≤15% | PRD 0,98–1,03 | PRB -0,05–0,05"
    for i, (nome, met, prb) in enumerate(linhas_ind):
        r = 4 + i
        ultimo = i == len(linhas_ind) - 1
        vals = [nome, met["n"], round(met["razao_mediana"], 3), round(met["COD"], 1),
                round(met["COD_mediano"], 1), round(met["PRD"], 3), round(prb, 3), meta]
        for c, v in enumerate(vals):
            ws_ind.write(r, c, v, bold_fmt if ultimo and c == 0 else None)
    for c, largura in enumerate([100, 8, 14, 16, 18, 8, 8, 50]):
        if c > 0:
            ws_ind.set_column(c, c, largura)
    linha_nota = 4 + len(linhas_ind) + 1
    ws_ind.write(linha_nota, 0, "O COD (média) é sensível a casos extremos; use o COD (mediano) "
                                "como referência mais robusta.", nota_fmt)
    ws_ind.write(linha_nota + 2, 0, "O que significam esses indicadores (em palavras simples)", azul)
    explicacoes = [
        ("COD — Coeficiente de Dispersão",
         "Mede o quanto as avaliações do modelo variam de um imóvel para outro em relação ao valor "
         "típico. Quanto MENOR, mais consistente é o modelo. Referência: até 15%."),
        ("PRD — Price-Related Differential",
         "Verifica se o modelo trata melhor imóveis baratos ou caros. Ideal próximo de 1,0 "
         "(entre 0,98 e 1,03)."),
        ("PRB — Price-Related Bias",
         "Mesma ideia do PRD, de forma estatisticamente mais robusta. Ideal entre -0,05 e +0,05."),
        ("Razão mediana",
         "Quanto o modelo estima em relação ao valor da transação atualizado, no meio da "
         "distribuição. 1,0 = acerto em cheio na mediana."),
    ]
    r = linha_nota + 3
    for nome_ind, texto in explicacoes:
        ws_ind.write(r, 0, nome_ind, bold_fmt)
        r += 1
        ws_ind.write(r, 0, texto, wrap_fmt)
        ws_ind.set_row(r, 40)
        r += 2

    wb.close()
    _log(f"Pronto: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
