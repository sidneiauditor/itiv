# -*- coding: utf-8 -*-
"""Série IPCA (SGS/BCB 433) e deflação — substitui src.limpeza do pacote legado."""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date

import pandas as pd

URL_IPCA = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"


def baixar_serie_ipca() -> pd.DataFrame:
    req = urllib.request.Request(URL_IPCA, headers={"User-Agent": "ITIV-Avaliador/1.0"})
    ultimo_erro: Exception | None = None
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = json.loads(resp.read())
            break
        except Exception as exc:  # noqa: BLE001
            ultimo_erro = exc
            time.sleep(3)
    else:
        raise RuntimeError(f"Falha ao baixar série IPCA após 5 tentativas: {ultimo_erro}")
    serie = pd.DataFrame(dados)
    serie["data"] = pd.to_datetime(serie["data"], format="%d/%m/%Y")
    serie["valor"] = pd.to_numeric(serie["valor"], errors="coerce")
    return serie.sort_values("data").reset_index(drop=True)


def serie_ipca_de_linhas(linhas: list[tuple[date, float]]) -> pd.DataFrame:
    if not linhas:
        return pd.DataFrame(columns=["data", "valor"])
    return pd.DataFrame(
        {"data": pd.to_datetime([d for d, _ in linhas]), "valor": [v for _, v in linhas]}
    ).sort_values("data").reset_index(drop=True)


def construir_indice_deflator(serie_ipca: pd.DataFrame) -> pd.Series:
    fator_mensal = 1 + serie_ipca["valor"] / 100
    indice = fator_mensal.cumprod()
    indice_ref = indice.iloc[-1]
    indice_normalizado = indice / indice_ref * 100
    return pd.Series(indice_normalizado.values, index=serie_ipca["data"].dt.to_period("M"))


def deflacionar_valores(
    valores: pd.Series,
    datas: pd.Series,
    serie_ipca: pd.DataFrame,
) -> pd.Series:
    if serie_ipca is None or serie_ipca.empty:
        return pd.to_numeric(valores, errors="coerce")
    indice = construir_indice_deflator(serie_ipca)
    mes = pd.to_datetime(datas, errors="coerce").dt.to_period("M")
    idx_mes = mes.map(indice).fillna(100.0)
    vl = pd.to_numeric(valores, errors="coerce")
    return vl * (100.0 / idx_mes)


def var_tendencia(datas: pd.Series, data_ref: pd.Timestamp) -> pd.Series:
    dt = pd.to_datetime(datas, errors="coerce")
    meses = (data_ref.year - dt.dt.year) * 12 + (data_ref.month - dt.dt.month)
    return meses.clip(lower=0)
