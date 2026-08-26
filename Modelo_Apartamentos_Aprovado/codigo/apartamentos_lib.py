# -*- coding: utf-8 -*-
"""Funcoes e constantes reutilizaveis do pipeline de treino do modelo de
apartamentos (Etapa 4). Sem efeitos colaterais ao importar — usado por
treinar_modelo_apartamentos.py e grafico_confianca_sinalizados.py.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.neighbors import NearestNeighbors

from metricas_iaao_por_decil import metricas_razao, prb_global

PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
AMOSTRAS = PASTA / "amostras"
SEMENTE = 42
K_FOLDS = 10
K_VIZINHOS = 10

FEATURES_LGBM = ["LOG_AREA", "NUPAVIMENTOS", "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE",
                  "VAR_TENDENCIA", "VLCOORDGEOX", "VLCOORDGEOY", "CDSETORFISCAL", "KNN_PROXY"]
CAT_LGBM = ["CDSETORFISCAL"]


def preparar_area_saneamento(df):
    df = df.copy()
    df["_AREA_SANEAMENTO"] = np.exp(df["LOG_AREA"])
    return df


def calcular_knn_proxy(df_base_treino: pd.DataFrame, df_alvo: pd.DataFrame, k=K_VIZINHOS) -> np.ndarray:
    """Para cada linha de df_alvo, media do log(R$/m2) dos k vizinhos mais
    proximos EM df_base_treino (causal — nunca usa o proprio alvo como vizinho
    de si mesmo, pois df_base_treino e df_alvo sao particoes distintas ou,
    quando iguais, usamos k+1 vizinhos e descartamos o mais proximo = si mesmo)."""
    base = df_base_treino.copy()
    m2_base = base["VLTRANSACAO_DEFLACIONADO"] / np.exp(base["LOG_AREA"])
    base["_LOGM2"] = np.log(m2_base.where(m2_base > 0))
    base_ok = base.dropna(subset=["VLCOORDGEOX", "VLCOORDGEOY", "_LOGM2"])

    proxy = np.full(len(df_alvo), np.nan)
    if len(base_ok) < k + 1:
        return proxy

    mesmo_conjunto = df_alvo is df_base_treino
    kk = k + 1 if mesmo_conjunto else k
    nn = NearestNeighbors(n_neighbors=min(kk, len(base_ok))).fit(
        base_ok[["VLCOORDGEOX", "VLCOORDGEOY"]].to_numpy())

    alvo_coords = df_alvo[["VLCOORDGEOX", "VLCOORDGEOY"]].to_numpy()
    validos = df_alvo[["VLCOORDGEOX", "VLCOORDGEOY"]].notna().all(axis=1).to_numpy()
    if validos.sum() == 0:
        return proxy

    dist, idx = nn.kneighbors(alvo_coords[validos])
    logm2_vizinhos = base_ok["_LOGM2"].to_numpy()
    valores = []
    for linha in idx:
        vals = logm2_vizinhos[linha]
        if mesmo_conjunto:
            vals = vals[1:]  # descarta o vizinho mais proximo (o proprio ponto)
        valores.append(np.nanmean(vals))
    proxy[validos] = valores
    return proxy


def montar_X_y(df, mediana_proxy=None):
    X = df[FEATURES_LGBM].copy()
    X["CDSETORFISCAL"] = X["CDSETORFISCAL"].astype("category")
    if mediana_proxy is None:
        mediana_proxy = X["KNN_PROXY"].median()
    X["KNN_PROXY"] = X["KNN_PROXY"].fillna(mediana_proxy)
    y = np.log(df["VLTRANSACAO_DEFLACIONADO"])
    return X, y, mediana_proxy


def _setor_int(serie):
    """CDSETORFISCAL como inteiro; -1 = setor ausente (sentinela, vira sua propria dummy)."""
    return serie.fillna(-1).astype(int)


def montar_X_numerico(df, mediana_proxy=None):
    """Versao de montar_X_y para modelos do scikit-learn (que nao aceitam o tipo
    'category' do pandas): CDSETORFISCAL entra como o proprio codigo numerico do
    setor (-1 = ausente), consistente entre treino e validacao."""
    X, y, mediana_proxy = montar_X_y(df, mediana_proxy)
    X["CDSETORFISCAL"] = _setor_int(df["CDSETORFISCAL"])
    return X, y, mediana_proxy


def treinar_hedonico(df_treino):
    """OLS: log(valor deflacionado) ~ log(area) + pavimentos + andar + flag +
    tendencia + dummies de setor fiscal. Fundamentacao normativa (testes t/F)."""
    y = np.log(df_treino["VLTRANSACAO_DEFLACIONADO"])
    dummies_setor = pd.get_dummies(_setor_int(df_treino["CDSETORFISCAL"]), prefix="SETOR", drop_first=True)
    X = pd.concat([
        df_treino[["LOG_AREA", "NUPAVIMENTOS", "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE", "VAR_TENDENCIA"]]
        .fillna(0).reset_index(drop=True),
        dummies_setor.reset_index(drop=True),
    ], axis=1).astype(float)
    X = sm.add_constant(X)
    modelo = sm.OLS(y.reset_index(drop=True), X, missing="drop").fit()
    return modelo, X.columns


def prever_hedonico(modelo, colunas_treino, df_alvo):
    dummies_setor = pd.get_dummies(_setor_int(df_alvo["CDSETORFISCAL"]), prefix="SETOR", drop_first=True)
    X = pd.concat([
        df_alvo[["LOG_AREA", "NUPAVIMENTOS", "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE", "VAR_TENDENCIA"]]
        .fillna(0).reset_index(drop=True),
        dummies_setor.reset_index(drop=True),
    ], axis=1).astype(float)
    X = sm.add_constant(X, has_constant="add")
    X = X.reindex(columns=colunas_treino, fill_value=0.0)
    return modelo.predict(X).to_numpy()


def metricas_completas(pred_valor, preco_real):
    m = (pred_valor > 0) & (preco_real > 0)
    met = metricas_razao(pred_valor[m], preco_real[m])
    met["PRB"] = prb_global(pred_valor[m], preco_real[m])
    return met
