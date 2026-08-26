# -*- coding: utf-8 -*-
"""Inscrição relativa no setor fiscal (produção).

  LOG_INSCRICAO_REL = LOG_INSCRICAO - mediana(LOG_INSCRICAO | setor no treino)
  RANK_INSCRICAO_SETOR = percentil empírico da inscrição dentro do setor (0–1)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES_REL = ["LOG_INSCRICAO_REL", "RANK_INSCRICAO_SETOR"]


def _log_insc(df: pd.DataFrame) -> pd.Series:
    insc = pd.to_numeric(df["CDINSCRICAOIMOB"], errors="coerce")
    return np.log1p(insc.clip(lower=0))


def stats_setor_treino(df_treino: pd.DataFrame) -> pd.DataFrame:
    """Mediana e distribuição empírica de LOG_INSCRICAO por setor — só no treino."""
    tmp = df_treino.copy()
    tmp["LOG_INSCRICAO"] = _log_insc(tmp)
    tmp["CDSETORFISCAL"] = pd.to_numeric(tmp["CDSETORFISCAL"], errors="coerce")
    ok = tmp.dropna(subset=["CDSETORFISCAL", "LOG_INSCRICAO"])

    meds = []
    vals_por_setor: dict[float, np.ndarray] = {}
    for setor, g in ok.groupby("CDSETORFISCAL"):
        vals = np.sort(g["LOG_INSCRICAO"].to_numpy())
        vals_por_setor[float(setor)] = vals
        meds.append(
            {
                "CDSETORFISCAL": setor,
                "LOG_INSCRICAO_MED_SETOR": float(np.median(vals)),
                "n_setor": int(len(vals)),
            }
        )
    stats = pd.DataFrame(meds)
    stats.attrs["vals_por_setor"] = vals_por_setor
    return stats


def anexar_inscricao_relativa(
    df: pd.DataFrame,
    stats: pd.DataFrame,
) -> pd.DataFrame:
    out = df.copy()
    out["LOG_INSCRICAO"] = _log_insc(out)
    out["CDSETORFISCAL"] = pd.to_numeric(out["CDSETORFISCAL"], errors="coerce")

    med = stats.set_index("CDSETORFISCAL")["LOG_INSCRICAO_MED_SETOR"]
    out["LOG_INSCRICAO_MED_SETOR"] = out["CDSETORFISCAL"].map(med)
    med_global = float(stats["LOG_INSCRICAO_MED_SETOR"].median())
    out["LOG_INSCRICAO_MED_SETOR"] = out["LOG_INSCRICAO_MED_SETOR"].fillna(med_global)
    out["LOG_INSCRICAO_REL"] = out["LOG_INSCRICAO"] - out["LOG_INSCRICAO_MED_SETOR"]

    vals_map: dict[float, np.ndarray] = stats.attrs.get("vals_por_setor", {})
    ranks = []
    for setor, logi in zip(out["CDSETORFISCAL"].to_numpy(), out["LOG_INSCRICAO"].to_numpy()):
        if not np.isfinite(setor) or not np.isfinite(logi):
            ranks.append(np.nan)
            continue
        arr = vals_map.get(float(setor))
        if arr is None or len(arr) == 0:
            ranks.append(0.5)
            continue
        ranks.append(float(np.searchsorted(arr, logi, side="right") / len(arr)))
    out["RANK_INSCRICAO_SETOR"] = ranks
    return out
