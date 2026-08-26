# -*- coding: utf-8 -*-
"""ETAPA 4.3 — Chauvenet ITERATIVO (criterio consagrado, aplicacao iterativa
conforme NBR 14653-2 item B.3) sobre log(R$/m2), aplicado SOMENTE no treino
(IBAPE 7.6.7 / 7.9.1) — nunca na inferencia.

Iterativo: remove o ponto mais distante da media (se violar o limiar de
Chauvenet), recalcula media/desvio, repete ate nenhum ponto violar.
Aplicado por tipologia seria redundante aqui pois a base ja e' so
apartamentos — o agrupamento fica disponivel via parametro `grupos` para
reuso em outros contextos.

Uso: chamar aplicar_chauvenet_iterativo(df) dentro de cada fold de treino
(nunca no conjunto de validacao/teste do fold, nem no holdout).
"""
import numpy as np
import pandas as pd
from scipy.special import erfcinv


def chauvenet_thr(n: int) -> float:
    """Limite em desvios-padrao do criterio de Chauvenet para tamanho n."""
    return np.sqrt(2) * erfcinv(1.0 / (2 * n)) if n > 1 else np.inf


def _iterar_grupo(x: np.ndarray) -> np.ndarray:
    """Retorna mascara booleana (True = mantido) apos Chauvenet iterativo."""
    mantido = np.ones(len(x), dtype=bool)
    while mantido.sum() > 2:
        sub = x[mantido]
        media, desvio = sub.mean(), sub.std(ddof=0)
        if desvio == 0:
            break
        z = np.abs((sub - media) / desvio)
        thr = chauvenet_thr(len(sub))
        pior_idx_local = np.argmax(z)
        if z[pior_idx_local] <= thr:
            break
        # remove o pior ponto (mapear de volta para o array original)
        idx_originais = np.where(mantido)[0]
        mantido[idx_originais[pior_idx_local]] = False
    return mantido


def aplicar_chauvenet_iterativo(df: pd.DataFrame, col_valor="VLTRANSACAO_DEFLACIONADO",
                                 col_area="_AREA_SANEAMENTO", grupos=None) -> pd.DataFrame:
    """Aplica Chauvenet iterativo em log(valor/area) e devolve o df filtrado
    (mantendo so as linhas que passaram). `grupos`: nome de coluna para
    agrupar (ex.: tipologia); None = trata tudo como um grupo so."""
    df = df.copy()
    vl = pd.to_numeric(df[col_valor], errors="coerce")
    ar = pd.to_numeric(df[col_area], errors="coerce") if col_area in df.columns else None
    if ar is None:
        raise ValueError(f"coluna de area '{col_area}' ausente — informe a area privativa")
    m2 = np.where(ar > 0, vl / ar, np.nan)
    log_m2 = np.log(np.where(m2 > 0, m2, np.nan))

    df["_LOG_M2_SANEAMENTO"] = log_m2
    validos = df["_LOG_M2_SANEAMENTO"].notna()

    if grupos is None:
        df["_grupo_tmp"] = "unico"
        grupos = "_grupo_tmp"

    manter = np.zeros(len(df), dtype=bool)
    manter[~validos.to_numpy()] = False  # descarta linhas sem log(m2) valido
    pos = pd.Series(np.arange(len(df)), index=df.index)

    for _, g in df[validos].groupby(grupos):
        idx_g = pos.loc[g.index].to_numpy()
        x = g["_LOG_M2_SANEAMENTO"].to_numpy()
        if len(x) < 5:
            manter[idx_g] = True  # grupo pequeno demais — sem saneamento
            continue
        mask_g = _iterar_grupo(x)
        manter[idx_g] = mask_g

    resultado = df[manter].drop(columns=["_LOG_M2_SANEAMENTO", "_grupo_tmp"], errors="ignore")
    return resultado


if __name__ == "__main__":
    from pathlib import Path
    PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV") / "amostras"
    df = pd.read_parquet(PASTA / "pool_treino_parametros.parquet")
    df["_AREA_SANEAMENTO"] = np.exp(df["LOG_AREA"])  # area original a partir do log

    print("=" * 70)
    print("DEMONSTRACAO — Chauvenet iterativo sobre o POOL inteiro")
    print("(no treino real, isso roda dentro de cada fold, so no treino do fold)")
    print("=" * 70)
    n0 = len(df)
    limpo = aplicar_chauvenet_iterativo(df)
    print(f"Antes: {n0:,} | Depois: {len(limpo):,} | Removidos: {n0 - len(limpo):,} "
          f"({(n0 - len(limpo)) / n0 * 100:.2f}%)")
