# -*- coding: utf-8 -*-
"""Configuração do serviço web (env + constantes de domínio)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]

PORTA = int(os.environ.get("ITIV_PORTA", "8766"))
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://itiv:itiv@localhost:5432/itiv",
)
GOOGLE_SV_KEY = os.environ.get("GOOGLE_SV_KEY", "")
MODELO_DIR = Path(os.environ.get("MODELO_DIR", str(_ROOT / "dados_modelo")))
ITIV_DADOS_DIR = Path(os.environ.get("ITIV_DADOS_DIR", str(_ROOT / "dados_importacao")))

VERSAO_MODELO = os.environ.get(
    "ITIV_VERSAO_MODELO",
    "idade + inscrição relativa (promovido 26/08/2026)",
)

# SIRGAS 2000 / UTM zona 24S — Salvador
CRS_UTM = "EPSG:31984"
CRS_GEOGRAFICO = "EPSG:4326"
LAT_MIN, LAT_MAX = -13.15, -12.70
LON_MIN, LON_MAX = -38.70, -38.25
R_TERRA = 6_371_000

ARQUIVO_MODELO = MODELO_DIR / "modelo_lightgbm_apartamentos.txt"

FEATURES_PRODUCAO_DEFAULT = [
    "LOG_AREA",
    "NUPAVIMENTOS",
    "ANDAR_UNIDADE",
    "FLAG_ANDAR_AUSENTE",
    "VAR_TENDENCIA",
    "VLCOORDGEOX",
    "VLCOORDGEOY",
    "CDSETORFISCAL",
    "KNN_PROXY",
    "IDADE_NA_TRANSACAO_IMP",
    "FLAG_ANO_AUSENTE",
    "FLAG_ANO_INVALIDO",
    "LOG_INSCRICAO_REL",
    "RANK_INSCRICAO_SETOR",
]

FILL_MEDIANAS_DEFAULT = {
    "IDADE_NA_TRANSACAO_IMP": 13.0,
    "VAR_TENDENCIA": 0.0,
    "NUPAVIMENTOS": 10.0,
    "ANDAR_UNIDADE": 5.0,
    "KNN_PROXY": 8.5,
}

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
