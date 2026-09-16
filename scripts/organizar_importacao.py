# -*- coding: utf-8 -*-
"""Reúne artefatos espalhados em dados_importacao/pronto/ com nomes canônicos.

Uso (na raiz do repositório):
  python -m scripts.organizar_importacao
"""
from __future__ import annotations

import fnmatch
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

from itiv_web.config import ITIV_DADOS_DIR, MODELO_DIR  # noqa: E402

# (padrões de busca, nome canônico em pronto/)
MAPA: list[tuple[list[str], str]] = [
    (["itiv_bruto.parquet", "*itiv*.parquet"], "itiv_bruto.parquet"),
    (["tabela_modelagem.parquet", "*modelagem*.parquet"], "tabela_modelagem.parquet"),
    (["ipca.csv", "serie_ipca.csv"], "ipca.csv"),
    (["Imoveis Salvador.parquet", "Imoveis Salvador.xlsx", "Imoveis*.parquet", "Imoveis*.xlsx"], "Imoveis Salvador.parquet"),
    (["Nascimento_Imovel.csv", "Nascimento*.csv"], "Nascimento_Imovel.csv"),
    (["pool_treino_parametros.parquet"], "pool_treino_parametros.parquet"),
    (["stats_setor_inscricao_treino.parquet", "stats_setor*.parquet"], "stats_setor_inscricao_treino.parquet"),
    (["vals_inscricao_por_setor.pkl"], "vals_inscricao_por_setor.pkl"),
    (["features_producao.json"], "features_producao.json"),
    (["fill_medians_producao.json"], "fill_medians_producao.json"),
    (["modelo_lightgbm_apartamentos.txt"], "modelo_lightgbm_apartamentos.txt"),
    (
        ["teste_final_previsoes_promovido.parquet", "teste_final_previsoes.parquet"],
        "teste_final_previsoes_promovido.parquet",
    ),
]

IGNORAR_DIR = {"pronto", "_origem", "legado_v20260714", "graficos"}


def _achar(base: Path, padroes: list[str]) -> Path | None:
    for pat in padroes:
        candidatos: list[Path] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(parte.casefold() in IGNORAR_DIR for parte in p.parts):
                continue
            if fnmatch.fnmatch(p.name.casefold(), pat.casefold()):
                candidatos.append(p)
        if candidatos:
            candidatos.sort(key=lambda x: (len(x.parts), str(x).casefold()))
            return candidatos[0]
    return None


def _copiar(origem: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        if destino.exists() and origem.samefile(destino):
            print(f"  ok    {destino} (já é o mesmo arquivo)", flush=True)
            return
    except OSError:
        pass
    if destino.exists() or destino.is_symlink():
        destino.unlink()
    try:
        destino.hardlink_to(origem)
        tipo = "link"
    except OSError:
        shutil.copy2(origem, destino)
        tipo = "copia"
    print(f"  {tipo}  {origem}  ->  {destino}", flush=True)


def main() -> None:
    base = ITIV_DADOS_DIR
    if not base.exists():
        raise SystemExit(f"Pasta inexistente: {base}")
    pronto = base / "pronto"
    pronto.mkdir(parents=True, exist_ok=True)

    print(f"Origem: {base.resolve()}", flush=True)
    print(f"Destino: {pronto.resolve()}", flush=True)
    faltando: list[str] = []
    for padroes, canonico in MAPA:
        achado = _achar(base, padroes)
        if achado is None:
            print(f"  AUSENTE: {canonico}  (buscou {padroes})", flush=True)
            faltando.append(canonico)
            continue
        dest_name = canonico
        if canonico.endswith(".parquet") and achado.suffix.lower() == ".xlsx":
            dest_name = achado.name
        _copiar(achado, pronto / dest_name)

    modelo_src = pronto / "modelo_lightgbm_apartamentos.txt"
    if modelo_src.exists():
        MODELO_DIR.mkdir(parents=True, exist_ok=True)
        _copiar(modelo_src, MODELO_DIR / "modelo_lightgbm_apartamentos.txt")

    origem_dir = base / "_origem"
    origem_dir.mkdir(exist_ok=True)
    for nome in ("entrega_equipe_20260615", "Modelo_Apartamentos_Aprovado", "projeto_itiv"):
        pasta = base / nome
        if pasta.is_dir():
            dest = origem_dir / nome
            if dest.exists():
                print(f"  _origem/{nome} já existe — pasta original mantida", flush=True)
                continue
            shutil.move(str(pasta), str(dest))
            print(f"  moveu {nome}/  ->  _origem/{nome}/", flush=True)

    if faltando:
        print("\nAlguns arquivos canônicos não foram encontrados:", flush=True)
        for n in faltando:
            print(f"  - {n}", flush=True)
        raise SystemExit(2)
    print("\nPronto. Rode: docker compose run --rm web python -m scripts.popular_base --recriar", flush=True)


if __name__ == "__main__":
    main()
