"""ETAPA 1 — Divisao aleatoria da amostra em treino/validacao/teste.
Conforme IBAPE 7.6.4 (particao aleatoria) e 7.8.4 (tres amostras p/ ML).
Proporcao 80/10/10. Semente fixa = 42 (reproduzivel e auditavel).
Salva tres arquivos separados.
"""
import pandas as pd
import numpy as np

BASE = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\base_limpa_normas.parquet"
SAIDA = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\amostras"

import os
os.makedirs(SAIDA, exist_ok=True)

df = pd.read_parquet(BASE)
n = len(df)
SEMENTE = 42

# Sorteio reproduzivel
rng = np.random.default_rng(SEMENTE)
perm = rng.permutation(n)
n_treino = int(n * 0.80)
n_val = int(n * 0.10)

idx_treino = perm[:n_treino]
idx_val = perm[n_treino:n_treino + n_val]
idx_teste = perm[n_treino + n_val:]

treino = df.iloc[idx_treino].copy()
val = df.iloc[idx_val].copy()
teste = df.iloc[idx_teste].copy()

treino.to_parquet(f"{SAIDA}/treino.parquet", index=False)
val.to_parquet(f"{SAIDA}/validacao.parquet", index=False)
teste.to_parquet(f"{SAIDA}/teste.parquet", index=False)

print(f"Base total: {n:,}")
print(f"Semente: {SEMENTE}")
print(f"  treino    : {len(treino):,} ({len(treino)/n*100:.1f}%)")
print(f"  validacao : {len(val):,} ({len(val)/n*100:.1f}%)")
print(f"  teste     : {len(teste):,} ({len(teste)/n*100:.1f}%)")
print(f"  SOMA      : {len(treino)+len(val)+len(teste):,} (deve ser {n:,})")

# Conferir que nao ha sobreposicao
sids = set(treino['SQTRANSMISSAO']) | set(val['SQTRANSMISSAO']) | set(teste['SQTRANSMISSAO'])
print(f"  IDs unicos somados: {len(sids):,} (sem sobreposicao se = {n:,})")

# Distribuicao por tipologia em cada
print("\nProporcao por tipologia (deve ser parecida nos tres):")
for nome, d in [("treino", treino), ("val", val), ("teste", teste)]:
    top = d['DSSUBUNIDADE'].value_counts(normalize=True).head(4).mul(100).round(1).to_dict()
    print(f"  {nome:9s}: {top}")
