# -*- coding: utf-8 -*-
"""
Avaliacao em lote — todas as transacoes de Apartamento da base ITIV.

Roda o modelo novo (LightGBM + hedonica, aprovados 14/07/2026) sobre todas as
transacoes de Apartamento e gera uma planilha Excel com:
  SQTRANSMISSAO, SETOR FISCAL, AREA PRIVATIVA, VALOR DECLARADO ORIGINAL,
  VALOR DECLARADO CORRIGIDO, INDICE DA CORRECAO (%), VLVENAL,
  VLVENALCORRIGIDO, INDICE DA CORRECAO (%), ESTIMATIVA DO MODELO (LIGHTGBM),
  VALOR DA OPINIAO HEDONICA.

Escopo: apenas Apartamento com compra e venda registrada (unico tipo coberto
pelo modelo). Nao usa dados de anuncios.

Executar:  python gerar_avaliacao_lote_apartamentos.py
Gera:      Modelo_Apartamentos_Aprovado/Avaliacao_Lote_Apartamentos_ITIV.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

RAIZ = Path(__file__).resolve().parent.parent.parent  # .../ITIV
PASTA_MODELO = RAIZ / "Modelo_Apartamentos_Aprovado"
PASTA_APP_ANTIGO = RAIZ / "entrega_equipe_20260615"

sys.path.insert(0, str(PASTA_APP_ANTIGO))
sys.path.insert(0, str(PASTA_MODELO / "codigo"))

from src import config as cfg
from src.limpeza import carregar_ou_cachear_bruto

import apartamentos_lib as aplib

ARQUIVO_SAIDA = PASTA_MODELO / "Avaliacao_Lote_Apartamentos_ITIV.xlsx"


def main() -> None:
    print("Carregando dados e modelo...", flush=True)

    bruto = carregar_ou_cachear_bruto()
    bruto[cfg.COL_ID] = bruto[cfg.COL_ID].astype(int)
    apto = bruto[bruto[cfg.COL_TIPOLOGIA] == "Apartamento"].copy()
    print(f"  {len(apto):,} transacoes de Apartamento na base.")

    tabela = pd.read_parquet(cfg.ARQUIVO_TABELA_MODELAGEM)
    tabela[cfg.COL_ID] = tabela[cfg.COL_ID].astype(int)

    pool = pd.read_parquet(PASTA_MODELO / "dados" / "amostras" / "pool_treino_parametros.parquet")
    teste_prev = pd.read_parquet(PASTA_MODELO / "dados" / "amostras" / "teste_final_previsoes.parquet")
    pool["KNN_PROXY"] = aplib.calcular_knn_proxy(pool, pool, k=aplib.K_VIZINHOS)
    categorias_setor = pd.Categorical(pool["CDSETORFISCAL"]).categories

    modelo_txt = (PASTA_MODELO / "dados" / "modelo_lightgbm_apartamentos.txt").read_text(encoding="utf-8")
    modelo_lgbm = lgb.Booster(model_str=modelo_txt)  # caminho acentuado quebra o fopen do LightGBM no Windows
    _, _, mediana_proxy = aplib.montar_X_y(pool)
    modelo_hed, colunas_hed = aplib.treinar_hedonico(pool)

    # --- engenharia de parametros (vetorizada) a partir do BRUTO ---
    area = pd.to_numeric(apto[cfg.COL_AREA_PRIVATIVA], errors="coerce")
    tem_area = area > 0
    n0 = len(apto)
    apto = apto[tem_area].copy()
    area = area[tem_area]
    removidos = n0 - len(apto)
    if removidos:
        print(f"  removidos {removidos} sem area privativa valida.")

    params = pd.DataFrame(index=apto.index)
    params["SQTRANSMISSAO"] = apto[cfg.COL_ID].values
    params["LOG_AREA"] = np.log(area.values)
    params["_AREA_PRIVATIVA"] = area.values

    pav = pd.to_numeric(apto[cfg.COL_PAVIMENTOS], errors="coerce")
    params["NUPAVIMENTOS"] = pav.where(pav > 0).values

    andar = pd.to_numeric(apto[cfg.COL_ANDAR], errors="coerce")
    params["FLAG_ANDAR_AUSENTE"] = (andar.isna() | (andar <= 0)).astype(int).values
    params["ANDAR_UNIDADE"] = andar.where(andar > 0, 0).values

    params["CDSETORFISCAL"] = apto[cfg.COL_SETOR].values
    params["VLCOORDGEOX"] = pd.to_numeric(apto[cfg.COL_COORD_X], errors="coerce").values
    params["VLCOORDGEOY"] = pd.to_numeric(apto[cfg.COL_COORD_Y], errors="coerce").values

    # VAR_TENDENCIA: reaproveita o valor calculado no treino para quem esta no
    # pool/teste; fora dessas tabelas (transacoes novas), usa 0 (sem defasagem).
    var_tend = pd.concat([
        pool[["SQTRANSMISSAO", "VAR_TENDENCIA"]],
        teste_prev[["SQTRANSMISSAO", "VAR_TENDENCIA"]],
    ]).drop_duplicates("SQTRANSMISSAO").set_index("SQTRANSMISSAO")["VAR_TENDENCIA"]
    params["VAR_TENDENCIA"] = params["SQTRANSMISSAO"].map(var_tend).fillna(0.0).values

    # --- previsoes ---
    print("Calculando KNN_PROXY (vizinhanca geografica)...", flush=True)
    params["KNN_PROXY"] = aplib.calcular_knn_proxy(pool, params, k=aplib.K_VIZINHOS)

    X, _, _ = aplib.montar_X_y(params.assign(VLTRANSACAO_DEFLACIONADO=1.0), mediana_proxy=mediana_proxy)
    X["CDSETORFISCAL"] = pd.Categorical(X["CDSETORFISCAL"], categories=categorias_setor)

    print("Rodando o modelo LightGBM...", flush=True)
    log_pred = modelo_lgbm.predict(X)
    previsto_lgbm = np.exp(log_pred)

    print("Rodando o modelo hedonico...", flush=True)
    previsto_hed = np.exp(aplib.prever_hedonico(modelo_hed, colunas_hed, params))

    # --- montagem da planilha de saida ---
    print("Montando planilha...", flush=True)
    tab_idx = tabela.drop_duplicates(cfg.COL_ID).set_index(cfg.COL_ID)
    apto_idx = apto.drop_duplicates(cfg.COL_ID).set_index(cfg.COL_ID)

    declarado_original = pd.to_numeric(apto_idx[cfg.COL_VALOR_TRANSACAO], errors="coerce")
    declarado_corrigido = pd.to_numeric(tab_idx[cfg.COL_VALOR_DEFL], errors="coerce").reindex(apto_idx.index)
    vlvenal = pd.to_numeric(apto_idx["VLVENALCADASTRO"], errors="coerce")
    vlvenal_corrigido = pd.to_numeric(apto_idx["VLVENALCORRIGIDO"], errors="coerce")

    def indice_pct(corrigido, original):
        with np.errstate(divide="ignore", invalid="ignore"):
            idx = (corrigido / original - 1) * 100
        return idx.where(original > 0)

    ids = apto[cfg.COL_ID].values

    saida = pd.DataFrame({
        "SQTRANSMISSAO": params["SQTRANSMISSAO"].values,
        "SETOR FISCAL": params["CDSETORFISCAL"].values,
        "AREA PRIVATIVA": params["_AREA_PRIVATIVA"].values,
        "VALOR DECLARADO ORIGINAL": declarado_original.reindex(ids).values,
        "VALOR DECLARADO CORRIGIDO": declarado_corrigido.reindex(ids).values,
    })
    saida["INDICE DA CORRECAO (%)"] = indice_pct(
        saida["VALOR DECLARADO CORRIGIDO"], saida["VALOR DECLARADO ORIGINAL"])
    saida["VLVENAL"] = vlvenal.reindex(ids).values
    saida["VLVENALCORRIGIDO"] = vlvenal_corrigido.reindex(ids).values
    saida["INDICE DA CORRECAO (%).1"] = indice_pct(saida["VLVENALCORRIGIDO"], saida["VLVENAL"])
    saida["ESTIMATIVA DO MODELO (LIGHTGBM)"] = previsto_lgbm
    saida["VALOR DA OPINIAO HEDONICA"] = previsto_hed

    # renomeia a segunda coluna repetida (venal) preservando os nomes pedidos
    saida.columns = [
        "SQTRANSMISSAO", "SETOR FISCAL", "AREA PRIVATIVA",
        "VALOR DECLARADO ORIGINAL", "VALOR DECLARADO CORRIGIDO",
        "INDICE DA CORRECAO (%)", "VLVENAL", "VLVENALCORRIGIDO", "INDICE DA CORRECAO (%)",
        "ESTIMATIVA DO MODELO (LIGHTGBM)", "VALOR DA OPINIAO HEDONICA",
    ]

    _salvar_excel(saida, ARQUIVO_SAIDA)
    print(f"\nPronto: {len(saida):,} avaliacoes gravadas em {ARQUIVO_SAIDA}", flush=True)


def _salvar_excel(df: pd.DataFrame, caminho: Path) -> None:
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Avaliacao Lote Apartamentos")
        ws = writer.sheets["Avaliacao Lote Apartamentos"]

        formato_rs = 'R$ #,##0.00'
        formato_pct = '0.00"%"'
        formato_area = '#,##0.00'
        colunas_rs = {"D", "E", "G", "H", "J", "K"}  # valores em R$
        colunas_pct = {"F", "I"}  # indices de correcao
        colunas_area = {"C"}

        for col_idx, coluna in enumerate(df.columns, start=1):
            letra = ws.cell(row=1, column=col_idx).column_letter
            largura = max(len(str(coluna)) + 2, 14)
            ws.column_dimensions[letra].width = largura
            if letra in colunas_rs:
                for row in range(2, len(df) + 2):
                    ws.cell(row=row, column=col_idx).number_format = formato_rs
            elif letra in colunas_pct:
                for row in range(2, len(df) + 2):
                    ws.cell(row=row, column=col_idx).number_format = formato_pct
            elif letra in colunas_area:
                for row in range(2, len(df) + 2):
                    ws.cell(row=row, column=col_idx).number_format = formato_area

        ws.freeze_panes = "A2"


if __name__ == "__main__":
    main()
