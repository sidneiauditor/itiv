# -*- coding: utf-8 -*-
"""SELIC (BCB SGS 432) na data da transação e lags de 3 e 6 meses."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PASTA_ITIV = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
CACHE_SELIC = PASTA_ITIV / "desafiante_idade" / "saida" / "selic_sgs432.csv"
# Taxa Selic meta (% a.a.) — série diária com platôs entre reuniões do Copom
SGS_SELIC = 432
SGS_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    "?formato=json&dataInicial={inicio}&dataFinal={fim}"
)
FEATURES_SELIC = ["SELIC_D0", "SELIC_M3", "SELIC_M6"]


def baixar_selic(forcar: bool = False) -> pd.DataFrame:
    CACHE_SELIC.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_SELIC.exists() and not forcar:
        selic = pd.read_csv(CACHE_SELIC, parse_dates=["data"])
        return selic.sort_values("data").reset_index(drop=True)

    fim = date.today().strftime("%d/%m/%Y")
    # Janela a partir de 2020 cobre o ITIV 2021–2026 e evita payload grande demais.
    url = SGS_URL.format(codigo=SGS_SELIC, inicio="01/01/2020", fim=fim)
    print(f"Baixando SELIC (SGS {SGS_SELIC})...", flush=True)
    resp = requests.get(
        url,
        timeout=90,
        headers={"Accept": "application/json", "User-Agent": "SEFAZ-ITIV/1.0"},
    )
    resp.raise_for_status()
    if not (resp.text or "").strip():
        raise RuntimeError(f"BCB retornou corpo vazio para SELIC ({url})")
    selic = pd.DataFrame(resp.json())
    selic["data"] = pd.to_datetime(selic["data"], dayfirst=True)
    selic["valor"] = pd.to_numeric(selic["valor"], errors="coerce")
    selic = selic.dropna().sort_values("data").reset_index(drop=True)
    selic.to_csv(CACHE_SELIC, index=False, encoding="utf-8-sig")
    print(f"Cache SELIC: {CACHE_SELIC} ({len(selic):,} pontos)", flush=True)
    return selic


def _lookup_asof(datas: pd.Series, serie: pd.DataFrame) -> np.ndarray:
    """Para cada data, ultima SELIC disponivel naquele dia ou anterior (asof)."""
    base = pd.DataFrame({"data": pd.to_datetime(datas, errors="coerce")})
    base["_i"] = np.arange(len(base))
    ordem = base.sort_values("data")
    s = serie.rename(columns={"valor": "selic"}).sort_values("data")
    m = pd.merge_asof(
        ordem.dropna(subset=["data"]),
        s,
        on="data",
        direction="backward",
    )
    out = np.full(len(base), np.nan)
    out[m["_i"].to_numpy()] = m["selic"].to_numpy()
    return out


def anexar_selic(
    df: pd.DataFrame,
    selic: pd.DataFrame | None = None,
    *,
    col_data: str = "DATA_TRANSACAO",
) -> pd.DataFrame:
    """Acrescenta SELIC_D0, SELIC_M3 (≈90d), SELIC_M6 (≈180d)."""
    selic = selic if selic is not None else baixar_selic()
    out = df.copy()
    d0 = pd.to_datetime(out[col_data], errors="coerce")
    out["SELIC_D0"] = _lookup_asof(d0, selic)
    out["SELIC_M3"] = _lookup_asof(d0 - pd.Timedelta(days=90), selic)
    out["SELIC_M6"] = _lookup_asof(d0 - pd.Timedelta(days=180), selic)
    return out
