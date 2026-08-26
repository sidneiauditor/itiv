# -*- coding: utf-8 -*-
"""
Avaliacao sobre os DADOS TRATADOS que serviram de base para construir e
validar o modelo (pool_treino_parametros.parquet + teste_final_parametros.
parquet — 46.392 transacoes, ja limpas: filtro de plausibilidade +/-30% vs.
venal, deflacao IPCA e engenharia de parametros da Etapa 4).

Compara o VALOR DA TRANSACAO ATUALIZADO (VLTRANSACAO_DEFLACIONADO, ja pronto
nesta base) com a ESTIMATIVA DO MODELO (LightGBM). Para o teste_final, a
previsao ja esta pronta (teste_final_previsoes.parquet); para o pool_treino,
e calculada aqui rodando o mesmo modelo ja treinado (sem retreinar nada).

Gera STATUS DA AVALIACAO + JUSTIFICATIVA (tolerancia +/-15%, mesma logica
usada nas planilhas anteriores) e uma aba de Indicadores IAAO. Como esta
base ja teve os outliers extremos removidos no proprio tratamento (Etapa 4),
os indices PRD/PRB nao devem sofrer a distorcao vista na planilha bruta.

Executar:  python gerar_avaliacao_dados_tratados.py
Gera:      Modelo_Apartamentos_Aprovado/Avaliacao_Dados_Tratados_Modelo.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apartamentos_lib as aplib
from metricas_iaao_por_decil import metricas_razao, prb_global

PASTA_MODELO = Path(__file__).resolve().parent.parent
PASTA_AMOSTRAS = PASTA_MODELO / "dados" / "amostras"
ARQUIVO_SAIDA = PASTA_MODELO / "Avaliacao_Dados_Tratados_Modelo.xlsx"

TOLERANCIA = 0.15  # +/-15%, ancorado na meta normativa de COD <= 15% (IAAO/NBR 14653-2)

COMPATIVEL = "Compatível"
COMPATIVEL_ABAIXO = "Compatível (valor da transação abaixo do valor estimado pelo modelo)"
NECESSITA_AUDITOR = "Necessidade Avaliação por Auditor"
SUSPEITO = "Valor da Transação Suspeito (fora de padrão)"
FORA_ESCOPO = "Fora de Escopo do Modelo"

# Limite do "suspeito" (decisao do usuario, 17/07/2026): ancorado na pior
# amplitude de erro ja observada na validacao oficial do modelo (Etapa 5,
# amplitude_ic80_maxima_pct = 53,9%). O limite abaixo (100% de diferenca,
# ou seja, razao < 0,5 ou > 2,0) fica bem acima do pior caso ja visto no
# modelo, entao uma divergencia assim so se explica por erro de dado
# (digitacao, zero a mais etc.), nao por incerteza normal do modelo.
LIMITE_SUSPEITO_INF = 0.5
LIMITE_SUSPEITO_SUP = 2.0


def _fmt_rs(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


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
    dado (ex.: zero a mais na digitacao), nao uma divergencia real de
    mercado, e nao entra nem em Compativel nem em Auditor.
    """
    if pd.isna(estimativa) or estimativa <= 0:
        return (FORA_ESCOPO, "Sem estimativa do modelo para esta transação.")
    if pd.isna(valor_atualizado) or valor_atualizado <= 0:
        return (FORA_ESCOPO, "Valor da transação atualizado ausente ou inválido.")

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
    print("Carregando dados tratados (pool_treino + teste_final)...")
    pool = pd.read_parquet(PASTA_AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(PASTA_AMOSTRAS / "teste_final_parametros.parquet")
    teste_prev = pd.read_parquet(PASTA_AMOSTRAS / "teste_final_previsoes.parquet")
    print(f"  pool_treino: {len(pool):,} | teste_final: {len(teste):,}")

    pool["KNN_PROXY"] = aplib.calcular_knn_proxy(pool, pool, k=aplib.K_VIZINHOS)
    categorias_setor = pd.Categorical(pool["CDSETORFISCAL"]).categories

    print("Carregando o modelo LightGBM já treinado...")
    modelo_txt = (PASTA_MODELO / "dados" / "modelo_lightgbm_apartamentos.txt").read_text(encoding="utf-8")
    modelo_lgbm = lgb.Booster(model_str=modelo_txt)
    _, _, mediana_proxy = aplib.montar_X_y(pool)

    print("Calculando a previsão do modelo para o pool_treino (mesmo modelo, sem retreinar)...")
    X_pool, _, _ = aplib.montar_X_y(pool, mediana_proxy=mediana_proxy)
    X_pool["CDSETORFISCAL"] = pd.Categorical(X_pool["CDSETORFISCAL"], categories=categorias_setor)
    pool["ESTIMATIVA DO MODELO (LIGHTGBM)"] = np.exp(modelo_lgbm.predict(X_pool))

    teste_idx = teste_prev.set_index("SQTRANSMISSAO")
    teste["ESTIMATIVA DO MODELO (LIGHTGBM)"] = teste["SQTRANSMISSAO"].map(teste_idx["VALOR_PREVISTO_LGBM"])
    teste["VALOR_PREVISTO_HEDONICO"] = teste["SQTRANSMISSAO"].map(teste_idx["VALOR_PREVISTO_HEDONICO"])

    pool["RECORTE"] = "Pool de treino/validação cruzada"
    teste["RECORTE"] = "Teste final (holdout, nunca visto no treino)"
    if "VALOR_PREVISTO_HEDONICO" not in pool.columns:
        pool["VALOR_PREVISTO_HEDONICO"] = np.nan

    todos = pd.concat([pool, teste], ignore_index=True)
    print(f"  Total combinado: {len(todos):,}")

    print("Classificando...")
    resultados = [classificar(v, e) for v, e in
                  zip(todos["VLTRANSACAO_DEFLACIONADO"], todos["ESTIMATIVA DO MODELO (LIGHTGBM)"])]
    todos["STATUS DA AVALIAÇÃO"] = [r[0] for r in resultados]
    todos["JUSTIFICATIVA"] = [r[1] for r in resultados]

    contagem = todos["STATUS DA AVALIAÇÃO"].value_counts()
    print("\nDistribuição:", dict(contagem))

    # --- indicadores IAAO ---
    def calcular_indicadores(df):
        av = df["ESTIMATIVA DO MODELO (LIGHTGBM)"].to_numpy(float)
        sp = df["VLTRANSACAO_DEFLACIONADO"].to_numpy(float)
        met = metricas_razao(av, sp)
        prb = prb_global(av, sp)
        return met, prb

    linhas_ind = []
    for nome, df_sub in [("Pool de treino/validação cruzada", pool),
                          ("Teste final (holdout)", teste),
                          ("Total (pool + teste)", todos)]:
        met, prb = calcular_indicadores(df_sub)
        linhas_ind.append((nome, met, prb))
        print(f"  {nome}: n={met['n']:,} razão mediana={met['razao_mediana']:.3f} "
              f"COD(média)={met['COD']:.1f}% COD(mediano)={met['COD_mediano']:.1f}% "
              f"PRD={met['PRD']:.3f} PRB={prb:.3f}")

    print(f"\nGravando {ARQUIVO_SAIDA.name}...")
    colunas_saida = [
        "SQTRANSMISSAO", "RECORTE", "CDSETORFISCAL", "LOG_AREA", "NUPAVIMENTOS",
        "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE", "VAR_TENDENCIA",
        "VLTRANSACAO", "VLTRANSACAO_DEFLACIONADO", "VLVENALCADASTRO",
        "ESTIMATIVA DO MODELO (LIGHTGBM)", "VALOR_PREVISTO_HEDONICO",
        "STATUS DA AVALIAÇÃO", "JUSTIFICATIVA",
    ]
    saida = todos[colunas_saida].rename(columns={
        "VALOR_PREVISTO_HEDONICO": "VALOR DA OPINIÃO HEDÔNICA",
        "VLTRANSACAO": "VALOR DECLARADO ORIGINAL",
        "VLTRANSACAO_DEFLACIONADO": "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)",
        "VLVENALCADASTRO": "VLVENAL",
        "CDSETORFISCAL": "SETOR FISCAL",
        "LOG_AREA": "LOG(ÁREA PRIVATIVA)",
    })

    with pd.ExcelWriter(ARQUIVO_SAIDA, engine="xlsxwriter") as writer:
        saida.to_excel(writer, sheet_name="Avaliação", index=False)
        wb = writer.book
        ws = writer.sheets["Avaliação"]

        n_linhas, n_cols = saida.shape
        ws.autofilter(0, 0, n_linhas, n_cols - 1)
        ws.freeze_panes(1, 0)

        fmt_rs = wb.add_format({"num_format": "R$ #,##0.00"})
        fmt_compativel = wb.add_format({"bg_color": "#C6EFCE"})
        fmt_compativel_abaixo = wb.add_format({"bg_color": "#DDEBF7"})
        fmt_auditor = wb.add_format({"bg_color": "#FFC7CE"})
        fmt_suspeito = wb.add_format({"bg_color": "#FFEB9C"})
        fmt_fora = wb.add_format({"bg_color": "#F2F2F2"})
        fmt_status = {COMPATIVEL: fmt_compativel, COMPATIVEL_ABAIXO: fmt_compativel_abaixo,
                       NECESSITA_AUDITOR: fmt_auditor, SUSPEITO: fmt_suspeito, FORA_ESCOPO: fmt_fora}

        col_status = saida.columns.get_loc("STATUS DA AVALIAÇÃO")
        col_just = saida.columns.get_loc("JUSTIFICATIVA")
        for col_nome in ["VALOR DECLARADO ORIGINAL", "VALOR DA TRANSAÇÃO ATUALIZADO (IPCA)",
                         "VLVENAL", "ESTIMATIVA DO MODELO (LIGHTGBM)", "VALOR DA OPINIÃO HEDÔNICA"]:
            c = saida.columns.get_loc(col_nome)
            ws.set_column(c, c, 22, fmt_rs)
        ws.set_column(col_status, col_status, 55)
        ws.set_column(col_just, col_just, 70)

        status_vals = saida["STATUS DA AVALIAÇÃO"].to_numpy()
        for i in range(n_linhas):
            ws.write(i + 1, col_status, status_vals[i], fmt_status[status_vals[i]])

        # --- aba de indicadores IAAO ---
        ws_ind = wb.add_worksheet("Indicadores IAAO (Modelo)")
        azul = wb.add_format({"bold": True, "font_size": 13, "font_color": "#1A3A5C"})
        nota_fmt = wb.add_format({"italic": True, "font_size": 9, "font_color": "#666666"})
        cab_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1A3A5C", "align": "center"})
        bold_fmt = wb.add_format({"bold": True, "font_color": "#1A3A5C"})
        wrap_fmt = wb.add_format({"text_wrap": True, "valign": "top"})

        ws_ind.set_column(0, 0, 100)
        ws_ind.write(0, 0, "Indicadores IAAO — Estimativa do modelo (LightGBM) x Valor da Transação "
                            "Atualizado (dados TRATADOS, base do treino/validação do modelo)", azul)
        ws_ind.write(1, 0, "Base: pool_treino_parametros.parquet + teste_final_parametros.parquet — "
                            "já com filtro de plausibilidade ±30% vs. venal e deflação IPCA aplicados "
                            "na Etapa 4 (sem outliers extremos).", nota_fmt)

        cabecalho = ["Recorte", "n", "Razão mediana", "COD (média, %)", "COD (mediano, %)", "PRD", "PRB", "Meta IAAO"]
        for c, texto in enumerate(cabecalho):
            ws_ind.write(3, c, texto, cab_fmt)

        meta_combinada = "Razão 0,98–1,03 | COD ≤15% | PRD 0,98–1,03 | PRB -0,05–0,05"
        for i, (nome, met, prb) in enumerate(linhas_ind):
            r = 4 + i
            valores = [nome, met["n"], round(met["razao_mediana"], 3), round(met["COD"], 1),
                       round(met["COD_mediano"], 1), round(met["PRD"], 3), round(prb, 3), meta_combinada]
            for c, v in enumerate(valores):
                cel_fmt = bold_fmt if (c == 0 and i == len(linhas_ind) - 1) else None
                ws_ind.write(r, c, v, cel_fmt)

        larguras = [100, 8, 14, 16, 18, 8, 8, 50]
        for c, largura in enumerate(larguras):
            if c > 0:
                ws_ind.set_column(c, c, largura)

        r0 = 4 + len(linhas_ind) + 2
        ws_ind.write(r0, 0, "O que significam esses indicadores (em palavras simples)", azul)
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
             "atualizado. 1,0 = acerto em cheio na mediana."),
        ]
        r = r0 + 1
        for nome_ind, texto in explicacoes:
            ws_ind.write(r, 0, nome_ind, bold_fmt)
            r += 1
            ws_ind.write(r, 0, texto, wrap_fmt)
            ws_ind.set_row(r, 48)
            r += 2

    print(f"\nPronto: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
