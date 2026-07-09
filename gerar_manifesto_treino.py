# -*- coding: utf-8 -*-
"""MANIFESTO DE REPRODUTIBILIDADE — congela a "impressao digital" da base de treino.

Calcula o SHA-256 (impressao digital unica) de cada arquivo de dados e de cada
script do pipeline, registra contagens de linhas, versoes das bibliotecas e a
data — e salva tudo em manifesto_treino.json.

Para que serve: se qualquer byte de qualquer arquivo mudar, a impressao digital
muda. Ao auditar uma avaliacao no futuro (ex.: impugnacao de contribuinte),
basta recalcular e comparar com o manifesto para provar que a base e o codigo
sao exatamente os mesmos do treino.

NAO altera nenhum dado.
"""
import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
SAIDA = PASTA / "manifesto_treino.json"

ARQUIVOS_DADOS = [
    PASTA / "base_limpa_normas.parquet",
    PASTA / "amostras" / "treino.parquet",
    PASTA / "amostras" / "validacao.parquet",
    PASTA / "amostras" / "teste.parquet",
]
SCRIPTS_PIPELINE = [
    PASTA / "construir_base_limpa.py",
    PASTA / "etapa1_dividir_amostra.py",
    PASTA / "validar_consistencia.py",
    PASTA / "etapa3_comparar_outliers.py",
    PASTA / "verificacoes_pre_treino.py",
]

def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()

manifesto = {
    "gerado_em": datetime.now().isoformat(timespec="seconds"),
    "finalidade": (
        "Congelamento da base e do codigo para o treino do modelo de "
        "apartamentos (Etapa 4). Recalcular os SHA-256 e comparar com este "
        "arquivo prova que dados e codigo nao mudaram."
    ),
    "ambiente": {
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "sistema": platform.platform(),
    },
    "dados": {},
    "scripts": {},
}

print("Calculando impressoes digitais (SHA-256)...")
for arq in ARQUIVOS_DADOS:
    if not arq.exists():
        print(f"  [AUSENTE] {arq.name}")
        manifesto["dados"][arq.name] = {"erro": "arquivo ausente"}
        continue
    df = pd.read_parquet(arq)
    info = {
        "sha256": sha256_arquivo(arq),
        "bytes": arq.stat().st_size,
        "linhas": len(df),
        "colunas": len(df.columns),
    }
    manifesto["dados"][str(arq.relative_to(PASTA))] = info
    print(f"  {str(arq.relative_to(PASTA)):32s} {info['linhas']:>8,} linhas  {info['sha256'][:16]}...")

for arq in SCRIPTS_PIPELINE:
    if not arq.exists():
        manifesto["scripts"][arq.name] = {"erro": "arquivo ausente"}
        continue
    manifesto["scripts"][arq.name] = {"sha256": sha256_arquivo(arq)}
    print(f"  {arq.name:32s} (script)          {manifesto['scripts'][arq.name]['sha256'][:16]}...")

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(manifesto, f, ensure_ascii=False, indent=2)

print(f"\nManifesto salvo: {SAIDA}")
print("Guarde este arquivo junto com o modelo treinado.")
