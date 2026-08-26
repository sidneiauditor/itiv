# -*- coding: utf-8 -*-
"""
Mesma avaliacao (STATUS + JUSTIFICATIVA + Indicadores IAAO) aplicada agora a
"Informações ITIV 20260610.xlsx" — a planilha bruta/completa do ITIV (148.811
transacoes de TODAS as tipologias, fonte original de onde a base BRUTO usada
no restante do projeto e' carregada).

Valor de referencia (decisao do usuario, 15/07/2026): a coluna pronta
VLDECLARADOCORRIGIDO so cobre 27.812/148.811 linhas (18,7%), concentradas
numa janela de datas estreita (2021-2027) e sem relacao clara com a situacao
da transmissao — nao parece ser uma correcao sistematica sobre toda a base.
Por isso, o "valor da transacao atualizado" e recalculado aqui do zero, com
a MESMA formula/serie usada no pipeline de treino do modelo
(src.limpeza.deflacionar_ipca — IPCA/SGS 433 do Banco Central), aplicada
sobre VLTRANSACAO para toda transacao com valor declarado > 0 e data valida.
Isso cobre uma fatia muito maior da base do que a coluna pronta ou a
tabela_modelagem.parquet (que ja vem filtrada por outras etapas de limpeza).

As estimativas do modelo (LightGBM + hedonica) sao reaproveitadas do lote ja
calculado em Avaliacao_Lote_Apartamentos_ITIV.xlsx (mesma fonte de dados,
mesmo SQTRANSMISSAO) em vez de recalculadas, pois sao identicas.

Executar:  python gerar_status_avaliacao_raw.py
Gera:      ITIV/Informações ITIV 20260610 - Status.xlsx
"""
from __future__ import annotations

from pathlib import Path

import time
import numpy as np
import pandas as pd
import xlsxwriter

_T0 = time.time()


def _log(msg: str) -> None:
    print(f"[{time.time()-_T0:7.1f}s] {msg}", flush=True)

import sys
PASTA_APP_ANTIGO_CODIGO = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_APP_ANTIGO_CODIGO))
from metricas_iaao_por_decil import metricas_razao, prb_global

RAIZ = Path(__file__).resolve().parent.parent.parent  # .../ITIV
PASTA_MODELO = RAIZ / "Modelo_Apartamentos_Aprovado"
PASTA_APP_ANTIGO = RAIZ / "entrega_equipe_20260615"
ARQUIVO_ENTRADA = RAIZ / "Informações ITIV 20260610.xlsx"
ARQUIVO_LOTE = PASTA_MODELO / "Avaliacao_Lote_Apartamentos_ITIV.xlsx"
ARQUIVO_SAIDA = RAIZ / "Informações ITIV 20260610 - Status.xlsx"

sys.path.insert(0, str(PASTA_APP_ANTIGO))
from src import config as cfg
from src.limpeza import baixar_serie_ipca, deflacionar_ipca

TOLERANCIA = 0.15  # +/-15%, ancorado na meta normativa de COD <= 15% (IAAO/NBR 14653-2)

COMPATIVEL = "Compatível"
COMPATIVEL_ABAIXO = "Compatível (valor da transação abaixo do valor estimado pelo modelo)"
NECESSITA_AUDITOR = "Necessidade Avaliação por Auditor"
SUSPEITO = "Valor da Transação Suspeito (fora de padrão)"
FORA_ESCOPO = "Fora de Escopo do Modelo"

# Limite do "suspeito" (decisao do usuario, 17/07/2026): ancorado na pior
# amplitude de erro ja observada na validacao oficial do modelo (Etapa 5,
# amplitude_ic80_maxima_pct = 53,9%). Razao fora de 0,5-2,0 (diferenca > 100%)
# fica bem acima do pior caso ja visto no modelo — so se explica por erro de
# dado (digitacao, zero a mais etc.), nao por incerteza normal do modelo.
LIMITE_SUSPEITO_INF = 0.5
LIMITE_SUSPEITO_SUP = 2.0


def _fmt_rs(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def fracao_transmitida(vlfracaoterreno, vlfracaoconstrucao) -> float:
    """
    Fracao do imovel efetivamente transmitida (decisao do usuario, 17/07/2026):
    a estimativa do modelo e treinada e calibrada para o imovel INTEIRO
    (VLFRACAOTERRENO == 1,0), mas a base bruta tambem contem transmissoes de
    fracao/quinhao (ex.: venda de 50% de um apartamento). Comparar o valor
    declarado dessas transacoes parciais com a estimativa cheia gera
    divergencia artificial de ~1/fracao, sem ser erro real. Usa a fracao de
    terreno; se ausente/invalida, cai para a de construcao; se nenhuma for
    valida, assume 1,0 (imovel inteiro).
    """
    ft = pd.to_numeric(vlfracaoterreno, errors="coerce")
    fc = pd.to_numeric(vlfracaoconstrucao, errors="coerce")
    f = ft if pd.notna(ft) and 0 < ft <= 1 else fc
    if pd.isna(f) or f <= 0 or f > 1:
        return 1.0
    return float(f)


def classificar(valor_atualizado, estimativa):
    """
    Regra (decisao do usuario, 17/07/2026): a comparacao e sempre e unica com
    o valor da transacao atualizado (nunca venal/Base_Inferida). O risco de
    perda de arrecadacao so existe quando o MODELO estima ACIMA do valor da
    transacao (indicio de subavaliacao) — so esse caso vai para auditor.
    Quando o modelo estima ABAIXO do valor da transacao, o contribuinte ja
    pagou mais do que o modelo julga que o imovel vale: sem risco para a
    Prefeitura, entao recebe um status "Compativel" proprio (nao vai para
    auditor), mesmo estando fora da faixa de +/-15%.

    Excecao: se a diferenca entre modelo e valor passar de 100% (razao fora
    de 0,5-2,0), o caso e classificado como "suspeito" — provavel erro de
    dado, nao uma divergencia real de mercado, e nao entra nem em Compativel
    nem em Auditor.

    `estimativa` aqui ja deve vir ajustada pela fracao transmitida (ver
    fracao_transmitida) antes de chegar nesta funcao.
    """
    if pd.isna(estimativa) or estimativa <= 0:
        return (FORA_ESCOPO, "Imóvel não é Apartamento com compra e venda registrada, ou não foi "
                              "localizado na base ITIV — o modelo não gera estimativa para este caso.")
    if pd.isna(valor_atualizado) or valor_atualizado <= 0:
        return (FORA_ESCOPO, "Valor da transação atualizado ausente ou inválido (sem valor declarado "
                              "positivo ou sem data válida para aplicar a correção monetária) — não é "
                              "possível comparar com a estimativa do modelo.")

    razao = estimativa / valor_atualizado
    diferenca_pct = (razao - 1) * 100

    if razao < LIMITE_SUSPEITO_INF or razao > LIMITE_SUSPEITO_SUP:
        return (SUSPEITO,
                f"Estimativa do modelo ({_fmt_rs(estimativa)}) diverge {abs(diferenca_pct):.0f}% do valor "
                f"da transação atualizado ({_fmt_rs(valor_atualizado)}) — muito além do pior caso já "
                f"observado na validação do modelo (53,9%). Provável erro de dado (ex.: valor digitado "
                f"errado), não uma divergência real de mercado; recomenda-se conferir o cadastro antes "
                f"de qualquer análise.")

    if (1 - TOLERANCIA) <= razao <= (1 + TOLERANCIA):
        return (COMPATIVEL,
                f"Estimativa do modelo ({_fmt_rs(estimativa)}) está {abs(diferenca_pct):.1f}% "
                f"{'acima' if diferenca_pct >= 0 else 'abaixo'} do valor da transação atualizado "
                f"({_fmt_rs(valor_atualizado)}) — dentro da tolerância de ±{TOLERANCIA*100:.0f}% "
                f"(meta normativa de COD ≤ 15%, IAAO/NBR 14653-2).")

    if razao < (1 - TOLERANCIA):
        return (COMPATIVEL_ABAIXO,
                f"Estimativa do modelo ({_fmt_rs(estimativa)}) está {abs(diferenca_pct):.1f}% abaixo "
                f"do valor da transação atualizado ({_fmt_rs(valor_atualizado)}) — fora da tolerância "
                f"de ±{TOLERANCIA*100:.0f}%, mas sem risco de perda de arrecadação (o contribuinte já "
                f"pagou mais do que o modelo estima).")

    return (NECESSITA_AUDITOR,
            f"Estimativa do modelo ({_fmt_rs(estimativa)}) está {diferenca_pct:.1f}% acima do valor da "
            f"transação atualizado ({_fmt_rs(valor_atualizado)}) — fora da tolerância de "
            f"±{TOLERANCIA*100:.0f}%; indício de possível subavaliação, recomenda-se análise "
            f"individual do auditor fiscal.")


def main() -> None:
    _log(f"Carregando {ARQUIVO_ENTRADA.name} (148 mil linhas, ~1 min)...")
    df = pd.read_excel(ARQUIVO_ENTRADA, sheet_name="Exportar Planilha", engine="calamine")
    sql_df = pd.read_excel(ARQUIVO_ENTRADA, sheet_name="SQL", engine="calamine", header=None)
    _log(f"  {len(df):,} transações carregadas.")

    _log("Carregando estimativas do modelo (lote já calculado)...")
    lote = pd.read_excel(ARQUIVO_LOTE, engine="calamine")
    lote_idx = lote.drop_duplicates("SQTRANSMISSAO").set_index("SQTRANSMISSAO")

    df["ESTIMATIVA DO MODELO (LIGHTGBM)"] = df["SQTRANSMISSAO"].map(lote_idx["ESTIMATIVA DO MODELO (LIGHTGBM)"])
    df["VALOR DA OPINIAO HEDONICA"] = df["SQTRANSMISSAO"].map(lote_idx["VALOR DA OPINIAO HEDONICA"])

    _log("Ajustando estimativas por fracao transmitida (transacoes de fracao/quinhao)...")
    df["FRACAO_TRANSMITIDA"] = [
        fracao_transmitida(ft, fc)
        for ft, fc in zip(df["VLFRACAOTERRENO"], df["VLFRACAOCONSTRUCAO"])
    ]
    n_fracao_parcial = int((df["FRACAO_TRANSMITIDA"] < 1.0).sum())
    _log(f"  {n_fracao_parcial:,} transações com fração < 100% — estimativa e opinião hedônica "
         f"multiplicadas pela fração antes de comparar.")
    df["ESTIMATIVA DO MODELO (LIGHTGBM)"] = (
        df["ESTIMATIVA DO MODELO (LIGHTGBM)"] * df["FRACAO_TRANSMITIDA"]
    )
    df["VALOR DA OPINIAO HEDONICA"] = (
        df["VALOR DA OPINIAO HEDONICA"] * df["FRACAO_TRANSMITIDA"]
    )

    _log("Recalculando o valor da transação atualizado (IPCA, mesma fórmula do treino)...")
    ipca = baixar_serie_ipca()
    valida = (
        pd.to_numeric(df[cfg.COL_VALOR_TRANSACAO], errors="coerce").fillna(0) > 0
    ) & pd.to_datetime(df[cfg.COL_DATA], errors="coerce").notna()
    _log(f"  {valida.sum():,} / {len(df):,} linhas com valor declarado > 0 e data válida.")
    sub_defl = deflacionar_ipca(df.loc[valida, [cfg.COL_VALOR_TRANSACAO, cfg.COL_DATA]], ipca)
    valor_atualizado = pd.Series(np.nan, index=df.index)
    valor_atualizado.loc[valida] = sub_defl[cfg.COL_VALOR_DEFL].to_numpy()
    df["VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"] = valor_atualizado

    _log("Classificando...")
    resultados = [classificar(v, e) for v, e in
                  zip(valor_atualizado, df["ESTIMATIVA DO MODELO (LIGHTGBM)"])]
    df["STATUS DA AVALIAÇÃO"] = [r[0] for r in resultados]
    df["JUSTIFICATIVA"] = [r[1] for r in resultados]

    contagem = df["STATUS DA AVALIAÇÃO"].value_counts()
    _log("Distribuição: " + str(dict(contagem)))

    # --- indicadores IAAO (so' Compra e Venda; exclui "Suspeito" = provavel erro de dado) ---
    m = (
        df["DSTIPOTRANSACAO"].astype(str).str.startswith("Compra e Venda")
        & df["ESTIMATIVA DO MODELO (LIGHTGBM)"].notna()
        & (df["ESTIMATIVA DO MODELO (LIGHTGBM)"] > 0)
        & (df["VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"] > 0)
        & (df["STATUS DA AVALIAÇÃO"] != SUSPEITO)
    )
    av = df.loc[m, "ESTIMATIVA DO MODELO (LIGHTGBM)"].to_numpy(float)
    sp = df.loc[m, "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)"].to_numpy(float)
    met = metricas_razao(av, sp)
    prb = prb_global(av, sp)
    print(f"\nIndicadores IAAO (Compra e Venda, n={met['n']:,}): "
          f"razão mediana={met['razao_mediana']:.3f} COD(mediano)={met['COD_mediano']:.1f}% "
          f"PRD={met['PRD']:.3f} PRB={prb:.3f}")

    _log(f"Gravando {ARQUIVO_SAIDA.name} (escrita otimizada, linha a linha)...")
    wb = xlsxwriter.Workbook(str(ARQUIVO_SAIDA), {"constant_memory": True, "default_date_format": "dd/mm/yyyy"})
    ws = wb.add_worksheet("Exportar Planilha")

    n_linhas, n_cols = df.shape
    col_status = df.columns.get_loc("STATUS DA AVALIAÇÃO")
    col_just = df.columns.get_loc("JUSTIFICATIVA")

    cab_fmt_dado = wb.add_format({"bold": True, "bg_color": "#1A3A5C", "font_color": "white"})
    for c, nome_col in enumerate(df.columns):
        ws.write(0, c, nome_col, cab_fmt_dado)
    ws.autofilter(0, 0, n_linhas, n_cols - 1)
    ws.freeze_panes(1, 0)
    ws.set_column(col_status, col_status, 55)
    ws.set_column(col_just, col_just, 70)

    fmt_compativel = wb.add_format({"bg_color": "#C6EFCE"})
    fmt_compativel_abaixo = wb.add_format({"bg_color": "#DDEBF7"})
    fmt_auditor = wb.add_format({"bg_color": "#FFC7CE"})
    fmt_suspeito = wb.add_format({"bg_color": "#FFEB9C"})
    fmt_fora = wb.add_format({"bg_color": "#F2F2F2"})
    fmt_status = {COMPATIVEL: fmt_compativel, COMPATIVEL_ABAIXO: fmt_compativel_abaixo,
                  NECESSITA_AUDITOR: fmt_auditor, SUSPEITO: fmt_suspeito, FORA_ESCOPO: fmt_fora}

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

    _log("Linhas de dados gravadas. Gravando aba SQL...")
    ws_sql = wb.add_worksheet("SQL")
    for i, row in sql_df.iterrows():
        v = row[0]
        if pd.isna(v):
            continue
        ws_sql.write_string(i, 0, str(v))

    # --- aba de indicadores IAAO ---
    # obs.: merge_range() nao e compativel com constant_memory=True, entao o
    # texto vai so na coluna A, com a coluna bem larga (sem merge).
    ws_ind = wb.add_worksheet("Indicadores IAAO (Modelo)")
    azul = wb.add_format({"bold": True, "font_size": 13, "font_color": "#1A3A5C"})
    nota_fmt = wb.add_format({"italic": True, "font_size": 9, "font_color": "#666666"})
    cab_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1A3A5C", "align": "center"})
    wrap_fmt = wb.add_format({"text_wrap": True, "valign": "top"})
    bold_fmt = wb.add_format({"bold": True, "font_color": "#1A3A5C"})

    ws_ind.set_column(0, 0, 100)
    ws_ind.write(0, 0, "Indicadores IAAO — Estimativa do modelo (LightGBM) x Valor da Transação Atualizado (IPCA)", azul)
    ws_ind.write(1, 0, "Restrito a transações de 'Compra e Venda' (qualquer subtipo). Valor da transação "
                        "atualizado = VLTRANSACAO corrigido pelo IPCA (série 433, BCB), mesma fórmula do "
                        "pipeline de treino do modelo.", nota_fmt)

    cabecalho = ["Recorte", "n", "Razão mediana", "COD (média, %)", "COD (mediano, %)", "PRD", "PRB", "Meta IAAO"]
    for c, texto in enumerate(cabecalho):
        ws_ind.write(3, c, texto, cab_fmt)

    meta_combinada = "Razão 0,98–1,03 | COD ≤15% | PRD 0,98–1,03 | PRB -0,05–0,05"
    valores_ind = ["Todas as transações (2015–2026)", met["n"], round(met["razao_mediana"], 3),
                   round(met["COD"], 1), round(met["COD_mediano"], 1), round(met["PRD"], 3),
                   round(prb, 3), meta_combinada]
    for c, v in enumerate(valores_ind):
        ws_ind.write(4, c, v, bold_fmt if c == 0 else None)

    larguras = [100, 8, 14, 16, 18, 8, 8, 50]
    for c, largura in enumerate(larguras):
        if c > 0:
            ws_ind.set_column(c, c, largura)

    ws_ind.write(6, 0, "Transações classificadas como \"Valor da Transação Suspeito (fora de padrão)\" já "
                        "foram excluídas deste cálculo (prováveis erros de dado). Ainda assim, o COD "
                        "(média) pode ser sensível a casos extremos remanescentes; use o COD (mediano) "
                        "como referência mais robusta.", nota_fmt)

    ws_ind.write(8, 0, "O que significam esses indicadores (em palavras simples)", azul)
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
    r = 9
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
