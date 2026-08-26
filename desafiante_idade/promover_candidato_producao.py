# -*- coding: utf-8 -*-
"""Promove o candidato idade+inscrição relativa para produção.

- Arquiva o LightGBM aprovado em 14/07/2026
- Copia artefatos do pacote candidato para Modelo_Apartamentos_Aprovado/
- Atualiza LEIA-ME e registro de promoção
- NÃO altera o avaliador HTML (feito em separado)

  python -u desafiante_idade/promover_candidato_producao.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PASTA_ITIV = HERE.parent
APROVADO = PASTA_ITIV / "Modelo_Apartamentos_Aprovado"
CANDIDATO = PASTA_ITIV / "Modelo_Apartamentos_Candidato_Idade_20260811"
HOJE = date.today().isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not CANDIDATO.exists():
        raise SystemExit(f"Pacote candidato ausente: {CANDIDATO}")

    dados = APROVADO / "dados"
    codigo = APROVADO / "codigo"
    legado = dados / "legado_v20260714"
    legado.mkdir(parents=True, exist_ok=True)

    modelo_antigo = dados / "modelo_lightgbm_apartamentos.txt"
    if modelo_antigo.exists() and not (legado / "modelo_lightgbm_apartamentos.txt").exists():
        shutil.copy2(modelo_antigo, legado / "modelo_lightgbm_apartamentos.txt")
        print(f"Arquivado: {legado / 'modelo_lightgbm_apartamentos.txt'}", flush=True)

    # Modelo promovido (mesmo nome operacional do avaliador)
    src_modelo = CANDIDATO / "dados" / "modelo_lightgbm_candidato_idade_rel.txt"
    shutil.copy2(src_modelo, modelo_antigo)
    shutil.copy2(src_modelo, dados / "modelo_lightgbm_apartamentos_idade_rel.txt")

    copias = [
        ("dados/Nascimento_Imovel.csv", "dados/Nascimento_Imovel.csv"),
        ("dados/stats_setor_inscricao_treino.parquet", "dados/stats_setor_inscricao_treino.parquet"),
        ("dados/vals_inscricao_por_setor.pkl", "dados/vals_inscricao_por_setor.pkl"),
        ("dados/fill_medians_candidato.json", "dados/fill_medians_producao.json"),
        ("dados/features_candidato.json", "dados/features_producao.json"),
        ("dados/avaliacao_holdout_candidato.json", "dados/avaliacao_holdout_promovido.json"),
        (
            "dados/teste_final_previsoes_candidato.parquet",
            "dados/amostras/teste_final_previsoes_promovido.parquet",
        ),
        ("codigo/idade_features.py", "codigo/idade_features.py"),
        ("codigo/teste_inscricao_relativa_setor.py", "codigo/inscricao_relativa.py"),
    ]
    for rel_src, rel_dst in copias:
        src = CANDIDATO / rel_src
        dst = APROVADO / rel_dst
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            print(f"  AVISO: ausente {src}", flush=True)
            continue
        shutil.copy2(src, dst)
        print(f"  OK {rel_dst}", flush=True)

    # Ajuste do módulo de inscrição relativa: caminho e docstring
    insc = codigo / "inscricao_relativa.py"
    if insc.exists():
        txt = insc.read_text(encoding="utf-8")
        # Mantém funções; o avaliador importa FEATURES_REL / anexar / stats
        insc.write_text(txt, encoding="utf-8")

    # idade_features: preferir CSV do pacote aprovado quando existir
    idade_py = codigo / "idade_features.py"
    if idade_py.exists():
        txt = idade_py.read_text(encoding="utf-8")
        local_csv = 'PASTA_ITIV / "Modelo_Apartamentos_Aprovado" / "dados" / "Nascimento_Imovel.csv"'
        txt2 = txt.replace(
            "CSV_NASCIMENTO = PASTA_ITIV / \"Nascimento Imovel.csv\"",
            f"CSV_NASCIMENTO = {local_csv}\n"
            f"if not CSV_NASCIMENTO.exists():\n"
            f"    CSV_NASCIMENTO = PASTA_ITIV / \"Nascimento Imovel.csv\"",
        )
        idade_py.write_text(txt2, encoding="utf-8")

    features = json.loads((dados / "features_producao.json").read_text(encoding="utf-8"))
    holdout = json.loads((dados / "avaliacao_holdout_promovido.json").read_text(encoding="utf-8"))
    hc = holdout["holdout"]["idade_mais_rel"]

    registro = {
        "data_promocao": HOJE,
        "candidato": "idade_mais_rel",
        "pacote_origem": CANDIDATO.name,
        "modelo_anterior": "legado_v20260714/modelo_lightgbm_apartamentos.txt (14/07/2026)",
        "modelo_producao": "dados/modelo_lightgbm_apartamentos.txt",
        "features": features["candidato"],
        "holdout_idade_mais_rel": hc,
        "autorizacao": (
            "E-mail David Yukishigue Taira (SEFAZ) de 25/08/2026 ao Marcos José de Souza Costa: "
            "concordância com inclusão de depreciação/idade; sem novas sugestões; "
            "encerramento da revisão do Relatório de Inteligência Fiscal 114/2026."
        ),
        "sha256_modelo": sha256(modelo_antigo),
    }
    (dados / "registro_promocao_idade_rel.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    leia = f"""# Modelo de Apartamentos (ITIV) — produção com idade + inscrição relativa

**Promovido em:** {HOJE}  
**Candidato:** `idade_mais_rel` (pacote `{CANDIDATO.name}`)  
**Substitui:** LightGBM de 14/07/2026 (arquivado em `dados/legado_v20260714/`)

## O que mudou

O modelo em produção passa a usar, além dos 9 parâmetros originais:

- **idade** na data da transação (`IDADE_NA_TRANSACAO_IMP` + flags de ano ausente/inválido);
- **inscrição relativa no setor** (`LOG_INSCRICAO_REL`, `RANK_INSCRICAO_SETOR`).

## Holdout (candidato promovido)

| Métrica | Valor |
|---|---:|
| COD mediano | {hc['COD_mediano']:.3f}% |
| COD | {hc['COD']:.3f}% |
| PRD | {hc['PRD']:.4f} |
| PRB | {hc['PRB']:.4f} |

## Avaliador HTML

Execute `Avaliador Apartamentos.bat` (ou `app/avaliador_web_apartamentos.py`).  
Abra http://localhost:8766

## Artefatos de promoção

- `dados/registro_promocao_idade_rel.json`
- `dados/features_producao.json`
- `dados/fill_medians_producao.json`
- `dados/Nascimento_Imovel.csv`
- `dados/stats_setor_inscricao_treino.parquet`
- `dados/vals_inscricao_por_setor.pkl`
"""
    (APROVADO / "LEIA-ME.md").write_text(leia, encoding="utf-8")

    leia_cand = (CANDIDATO / "LEIA-ME.md").read_text(encoding="utf-8")
    banner = (
        f"\n\n---\n\n## Status atualizado em {HOJE}\n\n"
        f"**PROMOVIDO À PRODUÇÃO.** Artefatos copiados para "
        f"`Modelo_Apartamentos_Aprovado/`. Avaliador HTML atualizado.\n"
    )
    if "PROMOVIDO À PRODUÇÃO" not in leia_cand:
        (CANDIDATO / "LEIA-ME.md").write_text(leia_cand + banner, encoding="utf-8")

    print(f"\nPromoção concluída. SHA-256 modelo: {registro['sha256_modelo']}", flush=True)


if __name__ == "__main__":
    main()
