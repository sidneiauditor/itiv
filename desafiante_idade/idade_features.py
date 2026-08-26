# -*- coding: utf-8 -*-
"""Engenharia de idade a partir de Nascimento Imovel.csv (AACONSTRUCAO).

Regras de higiene (Relatorio_Analise_Nascimento_Imovel):
- ano valido apenas em [1500, ano_referencia]
- IDADE_NA_TRANSACAO = ano_transacao - AACONSTRUCAO
- flags para ausente / invalido; sem imputacao silenciosa
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PASTA_ITIV = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
CSV_NASCIMENTO = PASTA_ITIV / "Nascimento Imovel.csv"
ANO_REF_CADASTRO = 2026

FAIXAS_INSCRICAO = [
    ("<300k", 0, 300_000),
    ("300-900k", 300_000, 900_000),
    (">900k", 900_000, 10**12),
]

FAIXAS_IDADE = [
    ("0-5", 0, 5),
    ("6-15", 6, 15),
    ("16-30", 16, 30),
    ("31-50", 31, 50),
    ("50+", 51, 500),
]


def carregar_nascimento(caminho: Path | None = None) -> pd.DataFrame:
    """Retorna DataFrame unico por CDINSCRICAOIMOB com AACONSTRUCAO higienizado."""
    caminho = caminho or CSV_NASCIMENTO
    raw = pd.read_csv(
        caminho, sep=";", encoding="utf-8-sig",
        dtype={"CDINSCRICAOIMOB": "Int64", "AACONSTRUCAO": "float"},
        low_memory=False,
    )
    raw.columns = [c.strip().upper() for c in raw.columns]
    if "CDINSCRICAOIMOB" not in raw.columns or "AACONSTRUCAO" not in raw.columns:
        raise ValueError(f"CSV sem colunas esperadas: {list(raw.columns)}")

    raw = raw.dropna(subset=["CDINSCRICAOIMOB"])
    raw["CDINSCRICAOIMOB"] = raw["CDINSCRICAOIMOB"].astype(np.int64)
    # Ultima ocorrencia por inscricao (arquivo tende a ser estavel; conflito e raro)
    agrupado = (
        raw.sort_index()
        .drop_duplicates(subset=["CDINSCRICAOIMOB"], keep="last")
        [["CDINSCRICAOIMOB", "AACONSTRUCAO"]]
        .reset_index(drop=True)
    )
    return agrupado


def higienizar_ano(ano: pd.Series, ano_max: int | None = None) -> pd.Series:
    ano_max = ano_max or ANO_REF_CADASTRO
    a = pd.to_numeric(ano, errors="coerce")
    ok = a.notna() & (a >= 1500) & (a <= ano_max)
    out = a.where(ok)
    return out


def faixa_inscricao(insc: pd.Series) -> pd.Series:
    v = pd.to_numeric(insc, errors="coerce")
    out = pd.Series("(sem inscricao)", index=v.index, dtype=object)
    for nome, lo, hi in FAIXAS_INSCRICAO:
        out = out.where(~((v >= lo) & (v < hi)), nome)
    return out


def faixa_idade(idade: pd.Series) -> pd.Series:
    v = pd.to_numeric(idade, errors="coerce")
    out = pd.Series("(sem idade)", index=v.index, dtype=object)
    for nome, lo, hi in FAIXAS_IDADE:
        out = out.where(~((v >= lo) & (v <= hi)), nome)
    return out


def anexar_idade(
    df: pd.DataFrame,
    nascimento: pd.DataFrame | None = None,
    *,
    col_inscricao: str = "CDINSCRICAOIMOB",
    col_data: str = "DATA_TRANSACAO",
) -> pd.DataFrame:
    """Acrescenta AACONSTRUCAO, IDADE_NA_TRANSACAO e flags ao DataFrame de transacoes."""
    nasc = nascimento if nascimento is not None else carregar_nascimento()
    out = df.copy()
    out[col_inscricao] = pd.to_numeric(out[col_inscricao], errors="coerce")

    out = out.merge(nasc, on=col_inscricao, how="left", validate="many_to_one")

    data = pd.to_datetime(out[col_data], errors="coerce")
    ano_tx = data.dt.year
    # Sem data de transacao: usa ano de referencia cadastral (diagnostico / lote)
    ano_tx = ano_tx.fillna(ANO_REF_CADASTRO).astype(int)
    # Ano maximo de validade do AACONSTRUCAO = ano da transacao (nao o ano civil atual)
    a_const = pd.to_numeric(out["AACONSTRUCAO"], errors="coerce")
    ok = a_const.notna() & (a_const >= 1500) & (a_const <= ano_tx)
    out["AACONSTRUCAO_OK"] = a_const.where(ok)

    out["FLAG_ANO_AUSENTE"] = out["AACONSTRUCAO"].isna().astype(int)
    out["FLAG_ANO_INVALIDO"] = (
        out["AACONSTRUCAO"].notna() & out["AACONSTRUCAO_OK"].isna()
    ).astype(int)

    idade = ano_tx - out["AACONSTRUCAO_OK"]
    out["IDADE_NA_TRANSACAO"] = idade.where(idade.notna() & (idade >= 0))
    # Imputacao apenas para o modelo: mediana do conjunto + flag (nunca esconder ausencia)
    med = out["IDADE_NA_TRANSACAO"].median()
    out["IDADE_NA_TRANSACAO_IMP"] = out["IDADE_NA_TRANSACAO"].fillna(
        med if pd.notna(med) else 0.0
    )
    out["FAIXA_INSCRICAO"] = faixa_inscricao(out[col_inscricao])
    out["FAIXA_IDADE"] = faixa_idade(out["IDADE_NA_TRANSACAO"])
    return out


FEATURES_IDADE = ["IDADE_NA_TRANSACAO_IMP", "FLAG_ANO_AUSENTE", "FLAG_ANO_INVALIDO"]
