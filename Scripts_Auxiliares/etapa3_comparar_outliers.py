# -*- coding: utf-8 -*-
"""ETAPA 3 — Comparacao dos metodos de outlier sobre a AMOSTRA DE TREINO.
SO MEDE quantos cada metodo marcaria. NAO exclui. NAO altera dados.
Aplicado sobre log(R$/m2) dentro de cada tipologia (grupos comparaveis).
Metodos: Z-Score, IQR, Mahalanobis, Chauvenet (NBR 14653-2).
"""
import numpy as np
import pandas as pd
from scipy import stats

TREINO = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\amostras\treino.parquet"
df = pd.read_parquet(TREINO)

# valor/m2
ap = pd.to_numeric(df["VLAREAUSOPRIV"], errors="coerce")
at = pd.to_numeric(df["VLAREATERRENO"], errors="coerce")
area = ap.where(ap > 0, at)
vl = pd.to_numeric(df["VLTRANSACAO"], errors="coerce")
df["_AREA"] = area
df["_M2"] = np.where(area > 0, vl / area, np.nan)
df["_LOGM2"] = np.log(df["_M2"].where(df["_M2"] > 0))
df["_LOGAREA"] = np.log(df["_AREA"].where(df["_AREA"] > 0))
df["_TIP"] = df["DSSUBUNIDADE"].astype(str)

base = df[df["_LOGM2"].notna() & df["_LOGAREA"].notna()].copy()
n = len(base)
print(f"Treino com R$/m2 calculavel: {n:,} de {len(df):,}\n")

def chauvenet_thr(n):
    # criterio de Chauvenet: limite em desvios-padrao para tamanho n
    from scipy.special import erfcinv
    return np.sqrt(2) * erfcinv(1.0 / (2 * n)) if n > 1 else np.inf

flags = {m: np.zeros(n, dtype=bool) for m in ["Z-Score", "IQR", "Mahalanobis", "Chauvenet"]}
idx_arr = base.index.to_numpy()
pos = {ix: i for i, ix in enumerate(idx_arr)}

for tip, g in base.groupby("_TIP"):
    if len(g) < 5:
        continue
    x = g["_LOGM2"].to_numpy()
    gi = [pos[ix] for ix in g.index]

    # Z-Score (>3)
    z = np.abs((x - x.mean()) / x.std(ddof=0)) if x.std() > 0 else np.zeros_like(x)
    for k, f in zip(gi, z > 3): flags["Z-Score"][k] |= f

    # IQR (1.5)
    q1, q3 = np.percentile(x, [25, 75]); iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    out_iqr = (x < lo) | (x > hi)
    for k, f in zip(gi, out_iqr): flags["IQR"][k] |= f

    # Chauvenet
    thr = chauvenet_thr(len(g))
    out_ch = z > thr if x.std() > 0 else np.zeros_like(x, dtype=bool)
    for k, f in zip(gi, out_ch): flags["Chauvenet"][k] |= f

    # Mahalanobis (bivariado: log area + log m2), chi2 2gl a 99%
    M = g[["_LOGAREA", "_LOGM2"]].to_numpy()
    if len(g) > 5 and np.linalg.matrix_rank(np.cov(M.T)) == 2:
        mu = M.mean(axis=0); cov = np.cov(M.T)
        inv = np.linalg.inv(cov)
        d2 = np.einsum("ij,jk,ik->i", M - mu, inv, M - mu)
        out_m = d2 > stats.chi2.ppf(0.99, df=2)
        for k, f in zip(gi, out_m): flags["Mahalanobis"][k] |= f

print("== Quantos cada metodo marcaria como outlier (treino) ==")
for m, f in flags.items():
    print(f"  {m:12s}: {f.sum():6,}  ({f.sum()/n*100:.1f}%)")

print("\n== Sobreposicao ==")
import itertools
for a, b in itertools.combinations(flags, 2):
    inter = (flags[a] & flags[b]).sum()
    print(f"  {a} & {b}: {inter:,}")
todos = flags["Z-Score"] & flags["IQR"] & flags["Mahalanobis"] & flags["Chauvenet"]
print(f"  marcados por TODOS os 4: {todos.sum():,}")

# exemplos do que o Chauvenet (norma) marcaria nos extremos
base = base.assign(_CH=flags["Chauvenet"])
ex = base[base["_CH"]].nlargest(5, "_M2")[["DSSUBUNIDADE","_AREA","VLTRANSACAO","_M2"]]
ex2 = base[base["_CH"]].nsmallest(5, "_M2")[["DSSUBUNIDADE","_AREA","VLTRANSACAO","_M2"]]
print("\n== Exemplos Chauvenet — R$/m2 mais ALTO ==")
print(ex.to_string(index=False))
print("== Exemplos Chauvenet — R$/m2 mais BAIXO ==")
print(ex2.to_string(index=False))
