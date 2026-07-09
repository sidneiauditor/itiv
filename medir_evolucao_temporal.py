# -*- coding: utf-8 -*-
"""MEDICAO — evolucao temporal dos precos (apartamentos, base limpa).

SO MEDE. Nao corrige, nao deflaciona, nao define criterio — a forma de tratar
o tempo (deflacao por indice, variavel de tendencia, ou ambas) e' decisao da
equipe (ver documento de decisoes).

Contexto factual: a Lista Final de Parametros do modelo NOVO nao contem
nenhuma variavel de tempo. O pipeline ANTIGO (producao) trata o tempo por
tres vias: deflacao IPCA (SGS 433), divisao treino/teste POR DATA e tendencia
temporal como variavel. Esta medicao dimensiona o quanto o tempo importa na
base nova.
"""
import numpy as np
import pandas as pd

BASE = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\base_limpa_normas.parquet"

df = pd.read_parquet(BASE, columns=["DSSUBUNIDADE", "DATA_TRANSACAO",
                                    "VLTRANSACAO", "VLAREAUSOPRIV"])
df = df[df["DSSUBUNIDADE"] == "Apartamento"].copy()

vl = pd.to_numeric(df["VLTRANSACAO"], errors="coerce")
ar = pd.to_numeric(df["VLAREAUSOPRIV"], errors="coerce")
m = (vl > 0) & (ar > 0)
df = df[m]
df["_M2"] = vl[m] / ar[m]
df["_ANO"] = pd.to_datetime(df["DATA_TRANSACAO"]).dt.year

print(f"Apartamentos com preco e area validos: {len(df):,}")
print(f"Periodo: {df['DATA_TRANSACAO'].min().date()} a {df['DATA_TRANSACAO'].max().date()}\n")

tab = df.groupby("_ANO").agg(
    n=("_M2", "size"),
    mediana_m2=("_M2", "median"),
    mediana_valor=("VLTRANSACAO", lambda s: pd.to_numeric(s, errors="coerce").median()),
)
base_m2 = tab["mediana_m2"].iloc[0]
tab["indice_m2"] = tab["mediana_m2"] / base_m2 * 100

print(f"{'ano':>5s} {'n':>8s} {'% base':>7s} {'mediana R$/m2':>14s} {'mediana valor':>14s} {'indice (1o ano=100)':>20s}")
for ano, row in tab.iterrows():
    print(f"{ano:>5d} {int(row['n']):>8,} {row['n']/len(df)*100:>6.1f}% "
          f"{row['mediana_m2']:>14,.0f} {row['mediana_valor']:>14,.0f} {row['indice_m2']:>20.1f}")

primeiro, ultimo = tab.index[0], tab.index[-1]
var_total = (tab.loc[ultimo, 'mediana_m2'] / tab.loc[primeiro, 'mediana_m2'] - 1) * 100
print(f"\nVariacao da mediana de R$/m2 de {primeiro} a {ultimo}: {var_total:+.1f}%")
print(f"  (atencao: {primeiro}-2020 somam {int(tab.loc[:2020, 'n'].sum())} transacoes — "
      "sem massa estatistica; a variacao acima nao e' representativa)")
if 2021 in tab.index:
    var_21 = (tab.loc[ultimo, 'mediana_m2'] / tab.loc[2021, 'mediana_m2'] - 1) * 100
    print(f"Variacao de 2021 a {ultimo} (anos com massa de dados): {var_21:+.1f}%")
print("\n(Medicao apenas — nenhum dado alterado, nenhum criterio definido.)")
