# -*- coding: utf-8 -*-
"""ETAPA 4.1 — Prepara a base de apartamentos para o treino, aplicando as
decisoes D1, D2 e D3 confirmadas em Decisoes_Consistencia_Modelo_Apartamentos.docx
(09/07/2026).

D1: remove os 12 SQTRANSMISSAO duplicados (mantem a 1a ocorrencia).
D2: remove as linhas duplicadas de [inscricao, data, valor] (mantem a 1a ocorrencia).
D3: exclui vendas anteriores a 03/2020; deflaciona o valor pelo IPCA (serie 433/BCB)
    ate a data de referencia (ultimo mes disponivel na serie) e cria variavel de
    tendencia temporal (meses desde a data de referencia).

Filtro da equipe (14/07/2026) — substitui o corte de vendas simbolicas
(VLTRANSACAO <= R$ 1,00) por um filtro de plausibilidade, para melhorar
PRD/PRB (transacoes com valores muito abaixo ou muito acima do venal):
  1. DSTIPOTRANSACAO == "Compra e Venda" (igualdade exata, apos strip)
  2. DSSUBUNIDADE == "Apartamento"
  3. VLITIV > 0
  4. |VLTRANSACAO - VLVENALCORRIGIDO| / VLVENALCORRIGIDO <= 0,30

Reserva 20% dos apartamentos restantes como TESTE FINAL (holdout, nunca usado em
treino ou ajuste de hiperparametros) e 80% como POOL para a validacao cruzada (D7).
Sorteio aleatorio reprodutivel, semente 42 (mesmo padrao do pipeline anterior).

Nao mexe em base_limpa_normas.parquet — le e filtra, sem alterar o arquivo original.
"""
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
BASE = PASTA / "base_limpa_normas.parquet"
SAIDA = PASTA / "amostras"
SAIDA.mkdir(exist_ok=True)

CHAVE_DUP = ["CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO"]
CORTE_TEMPORAL = pd.Timestamp("2020-03-01")
SEMENTE = 42
FRACAO_HOLDOUT = 0.20
LIMITE_DESVIO_VENAL = 0.30  # |transacao - venal corrigido| / venal corrigido — decisao da equipe (14/07/2026)


def baixar_ipca_433():
    """Serie 433 do SGS/BCB (IPCA variacao mensal, %). Retorna DataFrame mensal."""
    import time
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ultimo_erro = None
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                dados = json.loads(r.read())
            break
        except Exception as e:
            ultimo_erro = e
            time.sleep(3)
    else:
        raise RuntimeError(f"Falha ao baixar serie IPCA apos 5 tentativas: {ultimo_erro}")
    serie = pd.DataFrame(dados)
    serie["data"] = pd.to_datetime(serie["data"], format="%d/%m/%Y")
    serie["valor"] = pd.to_numeric(serie["valor"], errors="coerce")
    serie = serie.sort_values("data").reset_index(drop=True)
    return serie


def construir_indice_deflator(serie_ipca: pd.DataFrame) -> pd.Series:
    """Indice acumulado (base 100 no ultimo mes da serie = data de referencia)."""
    fator_mensal = 1 + serie_ipca["valor"] / 100
    indice = fator_mensal.cumprod()
    indice_ref = indice.iloc[-1]
    indice_normalizado = indice / indice_ref * 100
    return pd.Series(indice_normalizado.values, index=serie_ipca["data"].dt.to_period("M"))


print("=" * 70)
print("ETAPA 4.1 — Preparacao da base de treino (apartamentos)")
print("=" * 70)

df = pd.read_parquet(BASE)
df = df[df["DSSUBUNIDADE"] == "Apartamento"].copy()
n0 = len(df)
print(f"\nApartamentos na base limpa: {n0:,}")

# D1 — remove SQTRANSMISSAO duplicado (mantem 1a ocorrencia)
antes = len(df)
df = df.drop_duplicates(subset=["SQTRANSMISSAO"], keep="first")
print(f"D1 — apos remover SQTRANSMISSAO duplicado: {len(df):,} (-{antes - len(df)})")

# Filtro da equipe (14/07/2026) — substitui o corte de vendas simbolicas.
# Objetivo: melhorar PRD/PRB, removendo transacoes com valores muito abaixo ou
# muito acima do valor venal corrigido (que distorcem as metricas por media).
antes = len(df)
tipo_ok = df["DSTIPOTRANSACAO"].astype(str).str.strip() == "Compra e Venda"
df = df[tipo_ok].copy()
print(f"Filtro equipe (1) — tipo 'Compra e Venda' exato: {len(df):,} (-{antes - len(df)})")

antes = len(df)
itiv = pd.to_numeric(df["VLITIV"], errors="coerce")
df = df[itiv > 0].copy()
print(f"Filtro equipe (3) — VLITIV > 0: {len(df):,} (-{antes - len(df)})")

antes = len(df)
vt = pd.to_numeric(df["VLTRANSACAO"], errors="coerce")
vv = pd.to_numeric(df["VLVENALCORRIGIDO"], errors="coerce")
sem_venal = int((vv.isna() | (vv <= 0)).sum())
desvio = (vt - vv).abs() / vv
df = df[desvio <= LIMITE_DESVIO_VENAL].copy()
print(f"Filtro equipe (4) — desvio venal x transacao <= {LIMITE_DESVIO_VENAL:.0%}: "
      f"{len(df):,} (-{antes - len(df)})")
if sem_venal:
    print(f"  (desses removidos, {sem_venal} tinham VLVENALCORRIGIDO ausente ou <= 0 — "
          "excluidos pelo proprio filtro, pois o desvio nao e' calculavel)")

# D2 — remove duplicata de inscricao+data+valor (mantem 1a ocorrencia)
antes = len(df)
df = df.drop_duplicates(subset=CHAVE_DUP, keep="first")
print(f"D2 — apos remover duplicata inscricao+data+valor: {len(df):,} (-{antes - len(df)})")

# D3 — corte temporal (exclui pre-marco/2020)
antes = len(df)
df["DATA_TRANSACAO"] = pd.to_datetime(df["DATA_TRANSACAO"])
df = df[df["DATA_TRANSACAO"] >= CORTE_TEMPORAL].copy()
print(f"D3 — apos excluir vendas antes de {CORTE_TEMPORAL.date()}: {len(df):,} (-{antes - len(df)})")

# D3 — deflacao IPCA + variavel de tendencia
print("\nBaixando serie 433 (IPCA) do BCB...")
ipca = baixar_ipca_433()
data_ref = ipca["data"].max()
print(f"Serie IPCA: {ipca['data'].min().date()} a {data_ref.date()} ({len(ipca)} meses)")
indice = construir_indice_deflator(ipca)

df["_MES_TRANSACAO"] = df["DATA_TRANSACAO"].dt.to_period("M")
df["_INDICE_MES"] = df["_MES_TRANSACAO"].map(indice)
faltantes = df["_INDICE_MES"].isna().sum()
if faltantes:
    # Meses mais recentes que a serie do IPCA publicada (BCB ainda nao divulgou):
    # tratados como ja na data de referencia (indice 100, sem deflacao) — o mes
    # de referencia (maio/2026) e' o ultimo publicado, entao a diferenca e' de
    # no maximo poucas semanas.
    print(f"  [ATENCAO] {faltantes} transacoes em meses ainda nao publicados pelo "
          f"IPCA (apos {data_ref.strftime('%m/%Y')}) — tratadas como indice 100 "
          "(sem deflacao adicional).")
    df["_INDICE_MES"] = df["_INDICE_MES"].fillna(100.0)
df["VLTRANSACAO_DEFLACIONADO"] = pd.to_numeric(df["VLTRANSACAO"], errors="coerce") * (100.0 / df["_INDICE_MES"])
df["VAR_TENDENCIA"] = (
    (data_ref.year - df["DATA_TRANSACAO"].dt.year) * 12
    + (data_ref.month - df["DATA_TRANSACAO"].dt.month)
).clip(lower=0)  # meses entre a venda e a data de referencia (0 = mes de referencia ou posterior)
df = df.drop(columns=["_MES_TRANSACAO", "_INDICE_MES"])
print(f"Data de referencia da deflacao: {data_ref.date()}")
print(f"VAR_TENDENCIA: min={df['VAR_TENDENCIA'].min()} max={df['VAR_TENDENCIA'].max()}")

# Divisao holdout (teste final) x pool de treino/validacao cruzada (D7)
n = len(df)
rng = np.random.default_rng(SEMENTE)
perm = rng.permutation(n)
n_holdout = int(n * FRACAO_HOLDOUT)
idx_holdout = perm[:n_holdout]
idx_pool = perm[n_holdout:]

teste_final = df.iloc[idx_holdout].copy()
pool_treino = df.iloc[idx_pool].copy()

pool_treino.to_parquet(SAIDA / "pool_treino.parquet", index=False)
teste_final.to_parquet(SAIDA / "teste_final.parquet", index=False)

print(f"\n{'=' * 70}")
print(f"RESULTADO FINAL")
print(f"  base apartamentos (apos D1/D2/D3): {n:,}")
print(f"  pool_treino.parquet (80% p/ k-fold): {len(pool_treino):,}")
print(f"  teste_final.parquet (20% holdout):   {len(teste_final):,}")
sids = set(pool_treino["SQTRANSMISSAO"]) | set(teste_final["SQTRANSMISSAO"])
print(f"  IDs unicos somados: {len(sids):,} (sem sobreposicao se = {n:,})")
print("=" * 70)
