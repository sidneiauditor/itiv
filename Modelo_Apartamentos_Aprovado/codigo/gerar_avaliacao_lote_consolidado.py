# -*- coding: utf-8 -*-
"""
Avaliacao em lote sobre a planilha ITIV_Base_Consolidada_2025_2026_sem_id.xlsx
(abas "Dados 2025" e "Dados 2026"), rodando o modelo novo (LightGBM +
hedonica, aprovados 14/07/2026) sobre os Apartamentos encontrados.

Mapeamento pedido pelo usuario:
  Nosso_Numero -> SQTRANSMISSAO
  VT           -> VALOR DECLARADO ORIGINAL
  VVA          -> na pratica ja e o venal CORRIGIDO (bate com VLVENALCORRIGIDO
                  da base ITIV em 95,4% dos casos, nao com o venal original).
                  Por decisao do usuario: VVA vira VLVENALCORRIGIDO, e o
                  VLVENAL (original) e buscado na base ITIV (VLVENALCADASTRO)
                  pelo SQTRANSMISSAO.

Escopo: apenas Apartamento (unico tipo coberto pelo modelo). Sem uso de
anuncios. So entram linhas cujo Nosso_Numero (SQTRANSMISSAO) e encontrado na
base ITIV como Apartamento com area privativa valida.

Executar:  python gerar_avaliacao_lote_consolidado.py
Gera:      Modelo_Apartamentos_Aprovado/Avaliacao_Lote_Consolidado_2025_2026.xlsx
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
ARQUIVO_CONSOLIDADO = RAIZ / "ITIV_Base_Consolidada_2025_2026_sem_id.xlsx"

sys.path.insert(0, str(PASTA_APP_ANTIGO))
sys.path.insert(0, str(PASTA_MODELO / "codigo"))

from src import config as cfg
from src.limpeza import carregar_ou_cachear_bruto

import apartamentos_lib as aplib

ARQUIVO_SAIDA = PASTA_MODELO / "Avaliacao_Lote_Consolidado_2025_2026.xlsx"

COLUNAS_CONSOLIDADO = [
    "Nosso_Numero", "Ano_Exercicio", "Tipo_Transacao", "Data_Liberacao",
    "Data_Pagamento", "VT", "VVA", "Fracao_Terreno", "Fracao_Construcao",
    "Valor_Pago_SAT", "Base_Inferida", "Qtd_Pagamentos", "Atipica",
]


def _carregar_consolidado() -> pd.DataFrame:
    xl = pd.ExcelFile(ARQUIVO_CONSOLIDADO)
    partes = []
    for aba in ["Dados 2025", "Dados 2026"]:
        df = xl.parse(aba, header=2)
        df.columns = COLUNAS_CONSOLIDADO
        partes.append(df)
    cons = pd.concat(partes, ignore_index=True)
    cons["Nosso_Numero"] = pd.to_numeric(cons["Nosso_Numero"], errors="coerce")
    cons["VT"] = pd.to_numeric(cons["VT"], errors="coerce")
    cons["VVA"] = pd.to_numeric(cons["VVA"], errors="coerce")
    cons = cons.dropna(subset=["Nosso_Numero"])
    cons["Nosso_Numero"] = cons["Nosso_Numero"].astype(int)
    return cons.drop_duplicates("Nosso_Numero")


def main() -> None:
    print("Carregando planilha consolidada...", flush=True)
    cons = _carregar_consolidado()
    print(f"  {len(cons):,} guias na planilha consolidada (2025+2026).")

    print("Carregando base ITIV e modelo...", flush=True)
    bruto = carregar_ou_cachear_bruto()
    bruto[cfg.COL_ID] = bruto[cfg.COL_ID].astype(int)
    bruto = bruto.drop_duplicates(cfg.COL_ID)

    tabela = pd.read_parquet(cfg.ARQUIVO_TABELA_MODELAGEM)
    tabela[cfg.COL_ID] = tabela[cfg.COL_ID].astype(int)
    tabela = tabela.drop_duplicates(cfg.COL_ID)

    pool = pd.read_parquet(PASTA_MODELO / "dados" / "amostras" / "pool_treino_parametros.parquet")
    teste_prev = pd.read_parquet(PASTA_MODELO / "dados" / "amostras" / "teste_final_previsoes.parquet")
    pool["KNN_PROXY"] = aplib.calcular_knn_proxy(pool, pool, k=aplib.K_VIZINHOS)
    categorias_setor = pd.Categorical(pool["CDSETORFISCAL"]).categories

    modelo_txt = (PASTA_MODELO / "dados" / "modelo_lightgbm_apartamentos.txt").read_text(encoding="utf-8")
    modelo_lgbm = lgb.Booster(model_str=modelo_txt)  # caminho acentuado quebra o fopen do LightGBM no Windows
    _, _, mediana_proxy = aplib.montar_X_y(pool)
    modelo_hed, colunas_hed = aplib.treinar_hedonico(pool)

    # --- junta consolidado (Nosso_Numero) com a base ITIV (SQTRANSMISSAO) ---
    bruto_idx = bruto.set_index(cfg.COL_ID)
    match = cons["Nosso_Numero"].isin(bruto_idx.index)
    n_sem_match = (~match).sum()
    cons_match = cons[match].copy()
    print(f"  {match.sum():,} guias encontradas na base ITIV ({n_sem_match:,} sem correspondencia).")

    info = bruto_idx.loc[cons_match["Nosso_Numero"]].reset_index()
    apto_mask = info[cfg.COL_TIPOLOGIA] == "Apartamento"
    area_valida = pd.to_numeric(info[cfg.COL_AREA_PRIVATIVA], errors="coerce") > 0
    usar = (apto_mask & area_valida).values
    n_fora_escopo = (~apto_mask).sum()
    n_sem_area = (apto_mask & ~area_valida).sum()
    print(f"  {n_fora_escopo:,} fora de escopo (nao e Apartamento); "
          f"{n_sem_area:,} Apartamento sem area privativa valida.")

    cons_match = cons_match[usar].reset_index(drop=True)
    info = info[usar].reset_index(drop=True)
    print(f"  {len(cons_match):,} guias de Apartamento aptas para avaliacao pelo modelo.")

    # --- engenharia de parametros (vetorizada) ---
    area = pd.to_numeric(info[cfg.COL_AREA_PRIVATIVA], errors="coerce")
    params = pd.DataFrame()
    params["SQTRANSMISSAO"] = cons_match["Nosso_Numero"].values
    params["LOG_AREA"] = np.log(area.values)
    params["_AREA_PRIVATIVA"] = area.values
    params["_SETOR_FISCAL"] = info[cfg.COL_SETOR].values

    pav = pd.to_numeric(info[cfg.COL_PAVIMENTOS], errors="coerce")
    params["NUPAVIMENTOS"] = pav.where(pav > 0).values

    andar = pd.to_numeric(info[cfg.COL_ANDAR], errors="coerce")
    params["FLAG_ANDAR_AUSENTE"] = (andar.isna() | (andar <= 0)).astype(int).values
    params["ANDAR_UNIDADE"] = andar.where(andar > 0, 0).values

    params["CDSETORFISCAL"] = info[cfg.COL_SETOR].values
    params["VLCOORDGEOX"] = pd.to_numeric(info[cfg.COL_COORD_X], errors="coerce").values
    params["VLCOORDGEOY"] = pd.to_numeric(info[cfg.COL_COORD_Y], errors="coerce").values

    var_tend = pd.concat([
        pool[["SQTRANSMISSAO", "VAR_TENDENCIA"]],
        teste_prev[["SQTRANSMISSAO", "VAR_TENDENCIA"]],
    ]).drop_duplicates("SQTRANSMISSAO").set_index("SQTRANSMISSAO")["VAR_TENDENCIA"]
    params["VAR_TENDENCIA"] = params["SQTRANSMISSAO"].map(var_tend).fillna(0.0).values

    print("Calculando KNN_PROXY (vizinhanca geografica)...", flush=True)
    params["KNN_PROXY"] = aplib.calcular_knn_proxy(pool, params, k=aplib.K_VIZINHOS)

    X, _, _ = aplib.montar_X_y(params.assign(VLTRANSACAO_DEFLACIONADO=1.0), mediana_proxy=mediana_proxy)
    X["CDSETORFISCAL"] = pd.Categorical(X["CDSETORFISCAL"], categories=categorias_setor)

    print("Rodando o modelo LightGBM...", flush=True)
    previsto_lgbm = np.exp(modelo_lgbm.predict(X))

    print("Rodando o modelo hedonico...", flush=True)
    previsto_hed = np.exp(aplib.prever_hedonico(modelo_hed, colunas_hed, params))

    # --- valores declarado/venal ---
    print("Montando planilha...", flush=True)
    tab_idx = tabela.set_index(cfg.COL_ID)
    ids = cons_match["Nosso_Numero"].values

    declarado_original = cons_match["VT"].values  # por instrucao do usuario
    declarado_corrigido = pd.to_numeric(tab_idx[cfg.COL_VALOR_DEFL], errors="coerce").reindex(ids).values

    vlvenal_original = pd.to_numeric(info["VLVENALCADASTRO"], errors="coerce").values
    vlvenal_corrigido = cons_match["VVA"].values  # decisao: VVA da planilha e o venal ja corrigido

    def indice_pct(corrigido, original):
        original = np.asarray(original, dtype=float)
        corrigido = np.asarray(corrigido, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            idx = (corrigido / original - 1) * 100
        idx[~(original > 0)] = np.nan
        return idx

    saida = pd.DataFrame({
        "SQTRANSMISSAO": ids,
        "SETOR FISCAL": params["_SETOR_FISCAL"].values,
        "AREA PRIVATIVA": params["_AREA_PRIVATIVA"].values,
        "VALOR DECLARADO ORIGINAL": declarado_original,
        "VALOR DECLARADO CORRIGIDO": declarado_corrigido,
    })
    saida["INDICE DA CORRECAO (%)"] = indice_pct(
        saida["VALOR DECLARADO CORRIGIDO"], saida["VALOR DECLARADO ORIGINAL"])
    saida["VLVENAL"] = vlvenal_original
    saida["VLVENALCORRIGIDO"] = vlvenal_corrigido
    saida["INDICE DA CORRECAO (%).1"] = indice_pct(saida["VLVENALCORRIGIDO"], saida["VLVENAL"])
    saida["ESTIMATIVA DO MODELO (LIGHTGBM)"] = previsto_lgbm
    saida["VALOR DA OPINIAO HEDONICA"] = previsto_hed

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
        df.to_excel(writer, index=False, sheet_name="Avaliacao Lote Consolidado")
        ws = writer.sheets["Avaliacao Lote Consolidado"]

        formato_rs = 'R$ #,##0.00'
        formato_pct = '0.00"%"'
        formato_area = '#,##0.00'
        colunas_rs = {"D", "E", "G", "H", "J", "K"}
        colunas_pct = {"F", "I"}
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
