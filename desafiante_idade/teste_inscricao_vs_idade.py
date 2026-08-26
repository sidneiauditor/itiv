# -*- coding: utf-8 -*-
"""A/B: so inscricao × so idade × as duas (proposta Gabriel Ramos).

Inscricao entra como LOG_INSCRICAO = log1p(CDINSCRICAOIMOB) — cobertura ~100%.
Idade: IDADE_NA_TRANSACAO_IMP + flags (Nascimento Imovel).

Nao altera o modelo em producao.

Executar:
  python -u desafiante_idade/teste_inscricao_vs_idade.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PASTA_ITIV = HERE.parent
CODIGO = PASTA_ITIV / "Modelo_Apartamentos_Aprovado" / "codigo"
sys.path.insert(0, str(CODIGO))
sys.path.insert(0, str(HERE))

from idade_features import (  # noqa: E402
    FEATURES_IDADE,
    FAIXAS_INSCRICAO,
    anexar_idade,
    carregar_nascimento,
    faixa_inscricao,
)

from apartamentos_lib import (  # noqa: E402
    AMOSTRAS,
    CAT_LGBM,
    FEATURES_LGBM,
    K_VIZINHOS,
    SEMENTE,
    calcular_knn_proxy,
    metricas_completas,
    preparar_area_saneamento,
)
from saneamento_chauvenet_iterativo import aplicar_chauvenet_iterativo  # noqa: E402

warnings.filterwarnings("ignore")

SAIDA = HERE / "saida"
SAIDA.mkdir(parents=True, exist_ok=True)

FEATURES_INSCRICAO = ["LOG_INSCRICAO"]

PARAMS = {
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "n_estimators": 800,
    "num_leaves": 63,
    "random_state": SEMENTE,
    "verbosity": -1,
}


def anexar_inscricao(df: pd.DataFrame, col: str = "CDINSCRICAOIMOB") -> pd.DataFrame:
    out = df.copy()
    insc = pd.to_numeric(out[col], errors="coerce")
    out["LOG_INSCRICAO"] = np.log1p(insc.clip(lower=0))
    out["FLAG_INSCRICAO_AUSENTE"] = insc.isna().astype(int)
    if "FAIXA_INSCRICAO" not in out.columns:
        out["FAIXA_INSCRICAO"] = faixa_inscricao(insc)
    return out


def _montar(df, features, fill: dict):
    X = df[features].copy()
    X["CDSETORFISCAL"] = X["CDSETORFISCAL"].astype("category")
    for col, med in fill.items():
        if col in X.columns:
            X[col] = X[col].fillna(med)
    y = np.log(df["VLTRANSACAO_DEFLACIONADO"])
    return X, y


def _fill_stats(df, features):
    fill = {}
    for c in features:
        if c == "CDSETORFISCAL":
            continue
        if c in df.columns:
            fill[c] = float(df[c].median()) if df[c].notna().any() else 0.0
    return fill


def _metricas_faixa(pred, real, mascara) -> dict | None:
    m = mascara & (real > 0) & np.isfinite(pred) & np.isfinite(real)
    if m.sum() < 30:
        return {"n": int(m.sum()), "COD_mediano": None, "COD": None, "PRD": None}
    met = metricas_completas(pred[m], real[m])
    return {
        "n": int(m.sum()),
        "COD_mediano": float(met["COD_mediano"]),
        "COD": float(met["COD"]),
        "PRD": float(met["PRD"]),
        "razao_mediana": float(met["razao_mediana"]),
    }


def treinar_holdout(treino: pd.DataFrame, teste: pd.DataFrame, features: list[str], nome: str):
    print(f"\n--- {nome} | n_feat={len(features)} ---", flush=True)
    fill = _fill_stats(treino, features)
    Xtr, ytr = _montar(treino, features, fill)
    Xte, _ = _montar(teste, features, fill)
    model = lgb.LGBMRegressor(**PARAMS)
    cats = [c for c in CAT_LGBM if c in Xtr.columns]
    model.fit(Xtr, ytr, categorical_feature=cats)
    pred = np.exp(model.predict(Xte))
    real = teste["VLTRANSACAO_DEFLACIONADO"].to_numpy()
    met = metricas_completas(pred, real)
    imp = {
        f: int(v)
        for f, v in sorted(
            zip(features, model.feature_importances_.tolist()),
            key=lambda x: -x[1],
        )
    }
    foco = {
        k: imp[k]
        for k in FEATURES_IDADE + FEATURES_INSCRICAO
        if k in imp
    }
    print(
        f"  holdout CODmed={met['COD_mediano']:.3f}% COD={met['COD']:.3f}% "
        f"PRD={met['PRD']:.4f} razao={met['razao_mediana']:.4f}",
        flush=True,
    )
    if foco:
        print(f"  importancia idade/inscricao: {foco}", flush=True)

    # Estratificacao: faixa inscricao + cobertura de ano
    estrat = {"por_inscricao": {}, "por_ano_cobertura": {}}
    for nome_fx, lo, hi in FAIXAS_INSCRICAO:
        insc = pd.to_numeric(teste["CDINSCRICAOIMOB"], errors="coerce").to_numpy()
        mask = (insc >= lo) & (insc < hi)
        estrat["por_inscricao"][nome_fx] = _metricas_faixa(pred, real, mask)

    flag_aus = teste["FLAG_ANO_AUSENTE"].to_numpy() == 1
    estrat["por_ano_cobertura"]["com_ano"] = _metricas_faixa(pred, real, ~flag_aus)
    estrat["por_ano_cobertura"]["sem_ano"] = _metricas_faixa(pred, real, flag_aus)

    return {
        "nome": nome,
        "features": features,
        "holdout": {k: float(v) for k, v in met.items()},
        "importances": imp,
        "importances_foco": foco,
        "estratificado": estrat,
        "pred": pred,
    }


def main():
    print("A/B inscricao × idade × ambas", flush=True)
    nasc = carregar_nascimento()

    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")

    pool = anexar_idade(pool, nasc)
    teste = anexar_idade(teste, nasc)
    pool = anexar_inscricao(pool)
    teste = anexar_inscricao(teste)

    cov_idade = 100 * pool["IDADE_NA_TRANSACAO"].notna().mean()
    cov_insc = 100 * pool["LOG_INSCRICAO"].notna().mean()
    print(
        f"  Cobertura pool: idade={cov_idade:.1f}% | LOG_INSCRICAO={cov_insc:.1f}%",
        flush=True,
    )
    print(
        f"  Cobertura teste: idade={100*teste['IDADE_NA_TRANSACAO'].notna().mean():.1f}% "
        f"| LOG_INSCRICAO={100*teste['LOG_INSCRICAO'].notna().mean():.1f}%",
        flush=True,
    )
    # Correlacao proxy (onde ambas existem)
    ambos = pool["IDADE_NA_TRANSACAO"].notna() & pool["LOG_INSCRICAO"].notna()
    if ambos.sum() > 100:
        corr = pool.loc[ambos, "IDADE_NA_TRANSACAO"].corr(
            pool.loc[ambos, "LOG_INSCRICAO"]
        )
        print(f"  Corr(idade, log_inscricao) no pool={corr:.3f}", flush=True)

    pool_san = preparar_area_saneamento(pool)
    pool_limpo = aplicar_chauvenet_iterativo(pool_san).copy()
    pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)
    teste_p = teste.copy()
    teste_p["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste_p, k=K_VIZINHOS)

    base = list(FEATURES_LGBM)
    variantes = [
        ("baseline_aprovado", base),
        ("so_inscricao", base + FEATURES_INSCRICAO),
        ("so_idade", base + FEATURES_IDADE),
        ("idade_mais_inscricao", base + FEATURES_IDADE + FEATURES_INSCRICAO),
    ]

    resultados = []
    preds = {"SQTRANSMISSAO": teste_p["SQTRANSMISSAO"].to_numpy()}
    for nome, feats in variantes:
        r = treinar_holdout(pool_limpo, teste_p, feats, nome)
        preds[f"PRED_{nome}"] = r["pred"]
        del r["pred"]
        resultados.append(r)

    ranking = sorted(resultados, key=lambda x: x["holdout"]["COD_mediano"])
    melhor = ranking[0]
    base_cod = next(
        x["holdout"]["COD_mediano"] for x in resultados if x["nome"] == "baseline_aprovado"
    )

    resumo = {
        "feature_inscricao": "LOG_INSCRICAO = log1p(CDINSCRICAOIMOB)",
        "features_idade": FEATURES_IDADE,
        "cobertura_pool": {
            "idade_pct": float(cov_idade),
            "log_inscricao_pct": float(cov_insc),
        },
        "baseline_cod_mediano": float(base_cod),
        "melhor_modelo": melhor["nome"],
        "melhor_cod_mediano": float(melhor["holdout"]["COD_mediano"]),
        "ranking_cod_mediano": [
            {
                "nome": r["nome"],
                "COD_mediano": r["holdout"]["COD_mediano"],
                "COD": r["holdout"]["COD"],
                "PRD": r["holdout"]["PRD"],
                "razao_mediana": r["holdout"]["razao_mediana"],
                "delta_vs_baseline_pp": base_cod - r["holdout"]["COD_mediano"],
                "importances_foco": r["importances_foco"],
                "estratificado": r["estratificado"],
            }
            for r in ranking
        ],
        "modelos": resultados,
    }

    out_json = SAIDA / "comparativo_inscricao_vs_idade.json"
    out_json.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(preds).to_csv(SAIDA / "preds_inscricao_vs_idade.csv", index=False)

    linhas = [
        "# A/B inscricao × idade × ambas (proposta Gabriel Ramos)",
        "",
        "Proxy de idade via `LOG_INSCRICAO = log1p(CDINSCRICAOIMOB)` (cobertura ~100%).",
        f"Idade declarada: `{', '.join(FEATURES_IDADE)}` (Nascimento Imovel).",
        "",
        "| Modelo | COD mediano | Δ vs baseline (pp) | COD | PRD | Importância foco |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in ranking:
        delta = base_cod - r["holdout"]["COD_mediano"]
        foco = ", ".join(f"{k}={v}" for k, v in r["importances_foco"].items()) or "—"
        linhas.append(
            f"| {r['nome']} | {r['holdout']['COD_mediano']:.3f}% | {delta:+.3f} | "
            f"{r['holdout']['COD']:.2f}% | {r['holdout']['PRD']:.4f} | {foco} |"
        )

    linhas += [
        "",
        f"**Melhor modelo:** `{melhor['nome']}` "
        f"(COD mediano = {melhor['holdout']['COD_mediano']:.3f}%).",
        "",
        "## Por faixa de inscricao (COD mediano)",
        "",
        "| Modelo | <300k | 300-900k | >900k | com ano | sem ano |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in ranking:
        e = r["estratificado"]
        def _c(d, k):
            v = d.get(k) or {}
            x = v.get("COD_mediano")
            return f"{x:.2f}%" if x is not None else "—"
        linhas.append(
            f"| {r['nome']} | {_c(e['por_inscricao'], '<300k')} | "
            f"{_c(e['por_inscricao'], '300-900k')} | {_c(e['por_inscricao'], '>900k')} | "
            f"{_c(e['por_ano_cobertura'], 'com_ano')} | {_c(e['por_ano_cobertura'], 'sem_ano')} |"
        )

    linhas += [
        "",
        "## Interpretação",
        "",
        "- Se **so_inscricao** ≈ **so_idade**: a sacada do Gabriel (inscrição como idade) "
        "funciona na prática e cobre quem não tem ano de construção.",
        "- Se **idade_mais_inscricao** ganha: há sinal complementar (ritmo de cadastro ≠ idade física).",
        "- Se **so_idade** ganha e inscrição pouco ajuda: priorizar nascimento; inscrição fica como fallback.",
        "",
        f"Arquivos: `{out_json.name}`, `preds_inscricao_vs_idade.csv`.",
    ]
    nota = "\n".join(linhas) + "\n"
    (SAIDA / "Nota_AB_Inscricao_vs_Idade.md").write_text(nota, encoding="utf-8")
    (PASTA_ITIV / "Nota_AB_Inscricao_vs_Idade.md").write_text(nota, encoding="utf-8")

    print("\n=== RESUMO ===", flush=True)
    for r in ranking:
        delta = base_cod - r["holdout"]["COD_mediano"]
        print(
            f"  {r['nome']}: CODmed={r['holdout']['COD_mediano']:.3f}% "
            f"(delta={delta:+.3f} pp)",
            flush=True,
        )
    print(f"Melhor: {melhor['nome']}", flush=True)
    print(f"JSON: {out_json}", flush=True)


if __name__ == "__main__":
    main()
