"""Constroi e salva a base LIMPA de transmissoes conforme criterios da equipe + norma.

Criterios (decididos com o auditor, fundamentados em IBAPE 7.2.11):
  1. Situacao: Baixado, Liberado ou Em aberto (exclui Cancelado)
  2. Tipo: SOMENTE 'Compra e Venda' e 'Compra e venda de garagem' (igualdade exata;
     exclui impugnacao VVA, arrematacao, permuta, cessao, dacao, adjudicacao, etc.)
  3. Data: usa DTPAGAMENTO; se invalida, recupera por registro/lavratura/assinatura;
     descarta so quem nao tem nenhuma data valida (2004-2026)
  4. Fracao: somente transmissoes de 100% (VLFRACAOTERRENO == 1,0)
  5. VLTRANSACAO > 0

NAO aplica limite de area nem de valor/m2 — isso e' decisao posterior, so para a
amostra de TREINO, e nunca na inferencia (IBAPE 7.6.7 / 7.9.1).
"""
import pandas as pd
import numpy as np

ARQ = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\Informações ITIV 20260610.xlsx"
OUT = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\base_limpa_normas.parquet"

print("Lendo Excel bruto (104 colunas, ~148k linhas)... pode levar ~2 min")
df = pd.read_excel(ARQ, sheet_name="Exportar Planilha")
n0 = len(df)
print(f"Bruto: {n0:,}")

def data_serie(s):
    return pd.to_datetime(s, errors="coerce")
def valida(d):
    return d.between("2004-01-01", "2026-12-31")

# 1. Situacao
sit_ok = df["DSSITUACAOTRANSMISSAO"].isin(["Baixado", "Liberado", "Em aberto"])

# 2. Tipo — igualdade exata (sem impugnacao VVA)
tipos_validos = {"Compra e Venda", "Compra e venda de garagem"}
tipo_ok = df["DSTIPOTRANSACAO"].isin(tipos_validos)

# 3. Data unificada
dpag = data_serie(df["DTPAGAMENTO"])
dreg = data_serie(df["DTREGISTROCARTORIO"])
dlav = data_serie(df["DTLAVRATURA"])
dass = data_serie(df["DTASSINATURACONTRATO"])
data_unificada = dpag.where(valida(dpag))
for alt in (dreg, dlav, dass):
    data_unificada = data_unificada.where(valida(data_unificada), alt.where(valida(alt)))
data_ok = valida(data_unificada)
df["DATA_TRANSACAO"] = data_unificada

# 4. Fracao 100%
ft = pd.to_numeric(df["VLFRACAOTERRENO"], errors="coerce")
fracao_ok = (ft == 1.0)

# 5. Valor
vl_ok = pd.to_numeric(df["VLTRANSACAO"], errors="coerce") > 0

mask = sit_ok & tipo_ok & data_ok & fracao_ok & vl_ok
limpa = df[mask].copy()

print("\n--- Funil ---")
print(f"  apos situacao:           {sit_ok.sum():,}")
print(f"  apos tipo:               {(sit_ok & tipo_ok).sum():,}")
print(f"  apos data:               {(sit_ok & tipo_ok & data_ok).sum():,}")
print(f"  apos fracao 100%:        {(sit_ok & tipo_ok & data_ok & fracao_ok).sum():,}")
print(f"  apos valor>0 (FINAL):    {mask.sum():,}  ({mask.sum()/n0*100:.1f}% do bruto)")

limpa.to_parquet(OUT, index=False)
print(f"\nBase limpa salva: {OUT}")
print(f"Linhas: {len(limpa):,} | Colunas: {len(limpa.columns)}")
print(f"Periodo: {limpa['DATA_TRANSACAO'].min().date()} a {limpa['DATA_TRANSACAO'].max().date()}")
print("\nPor tipologia (DSSUBUNIDADE):")
print(limpa["DSSUBUNIDADE"].value_counts().head(10).to_string())
