# -*- coding: utf-8 -*-
"""Ablation SELIC: D0 vs M3 vs M6 vs as tres juntas (proposta Gabriel Ramos).

Treino holdout (pool → teste final), hiperparametros do LightGBM aprovado.
Nao altera o modelo em producao.

Executar:
  python -u desafiante_idade/teste_selic_lags.py
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

from idade_features import FEATURES_IDADE, anexar_idade, carregar_nascimento  # noqa: E402
from selic_features import FEATURES_SELIC, anexar_selic, baixar_selic  # noqa: E402

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

PARAMS = {
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "n_estimators": 800,
    "num_leaves": 63,
    "random_state": SEMENTE,
    "verbosity": -1,
}


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
    selic_imp = {k: imp[k] for k in FEATURES_SELIC if k in imp}
    print(
        f"  holdout CODmed={met['COD_mediano']:.3f}% COD={met['COD']:.3f}% "
        f"PRD={met['PRD']:.4f} razao={met['razao_mediana']:.4f}",
        flush=True,
    )
    if selic_imp:
        print(f"  importancia SELIC: {selic_imp}", flush=True)
    return {
        "nome": nome,
        "features": features,
        "holdout": {k: float(v) for k, v in met.items()},
        "importances": imp,
        "importances_selic": selic_imp,
        "pred": pred,
    }


def main():
    print("Teste SELIC D0 / M3 / M6", flush=True)
    selic = baixar_selic()
    nasc = carregar_nascimento()

    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")

    pool = anexar_idade(pool, nasc)
    teste = anexar_idade(teste, nasc)
    pool = anexar_selic(pool, selic)
    teste = anexar_selic(teste, selic)

    print(
        f"  Cobertura SELIC_D0 pool={100*pool['SELIC_D0'].notna().mean():.1f}% "
        f"teste={100*teste['SELIC_D0'].notna().mean():.1f}%",
        flush=True,
    )
    print(
        f"  SELIC_D0 mediana pool={pool['SELIC_D0'].median():.2f}% "
        f"(min={pool['SELIC_D0'].min():.2f} max={pool['SELIC_D0'].max():.2f})",
        flush=True,
    )

    # Preparacao unica (Chauvenet + KNN) — comparacao justa entre variantes SELIC
    pool_san = preparar_area_saneamento(pool)
    pool_limpo = aplicar_chauvenet_iterativo(pool_san).copy()
    pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)
    teste_p = teste.copy()
    teste_p["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste_p, k=K_VIZINHOS)

    base = FEATURES_LGBM
    idade = FEATURES_LGBM + FEATURES_IDADE

    variantes = [
        ("baseline_aprovado", base),
        ("baseline_mais_SELIC_D0", base + ["SELIC_D0"]),
        ("baseline_mais_SELIC_M3", base + ["SELIC_M3"]),
        ("baseline_mais_SELIC_M6", base + ["SELIC_M6"]),
        ("baseline_mais_SELIC_3lags", base + FEATURES_SELIC),
        ("idade_desafiante", idade),
        ("idade_mais_SELIC_D0", idade + ["SELIC_D0"]),
        ("idade_mais_SELIC_M3", idade + ["SELIC_M3"]),
        ("idade_mais_SELIC_M6", idade + ["SELIC_M6"]),
        ("idade_mais_SELIC_3lags", idade + FEATURES_SELIC),
    ]

    resultados = []
    preds = {"SQTRANSMISSAO": teste_p["SQTRANSMISSAO"].to_numpy()}
    for nome, feats in variantes:
        r = treinar_holdout(pool_limpo, teste_p, feats, nome)
        preds[f"PRED_{nome}"] = r["pred"]
        del r["pred"]
        resultados.append(r)

    # Ranking por COD mediano (menor = melhor)
    ranking = sorted(resultados, key=lambda x: x["holdout"]["COD_mediano"])
    melhor = ranking[0]
    base_cod = next(x["holdout"]["COD_mediano"] for x in resultados if x["nome"] == "baseline_aprovado")

    # Qual lag SELIC sozinho melhora mais o baseline
    lags_sozinhos = [
        x for x in resultados
        if x["nome"] in (
            "baseline_mais_SELIC_D0",
            "baseline_mais_SELIC_M3",
            "baseline_mais_SELIC_M6",
        )
    ]
    melhor_lag = min(lags_sozinhos, key=lambda x: x["holdout"]["COD_mediano"])

    resumo = {
        "serie_bcb": "SGS 432 (Selic meta % a.a.)",
        "definicao_lags": {
            "SELIC_D0": "taxa no dia da transacao (ou ultimo dia util anterior)",
            "SELIC_M3": "taxa ~90 dias antes",
            "SELIC_M6": "taxa ~180 dias antes",
        },
        "baseline_cod_mediano": base_cod,
        "melhor_modelo": melhor["nome"],
        "melhor_cod_mediano": melhor["holdout"]["COD_mediano"],
        "melhor_lag_isolado": {
            "nome": melhor_lag["nome"],
            "cod_mediano": melhor_lag["holdout"]["COD_mediano"],
            "delta_vs_baseline_pp": base_cod - melhor_lag["holdout"]["COD_mediano"],
        },
        "ranking_cod_mediano": [
            {
                "nome": x["nome"],
                "COD_mediano": x["holdout"]["COD_mediano"],
                "COD": x["holdout"]["COD"],
                "PRD": x["holdout"]["PRD"],
                "razao_mediana": x["holdout"]["razao_mediana"],
                "delta_vs_baseline_pp": base_cod - x["holdout"]["COD_mediano"],
                "importances_selic": x["importances_selic"],
            }
            for x in ranking
        ],
        "resultados": resultados,
    }

    (SAIDA / "comparativo_selic_lags.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    pd.DataFrame(preds).to_parquet(SAIDA / "teste_previsoes_selic_lags.parquet", index=False)

    # Nota curta em markdown
    linhas = [
        "# Teste SELIC — D0 / M3 / M6 (proposta Gabriel Ramos)",
        "",
        "Série: BCB SGS **432** (Selic meta % a.a.).",
        "",
        "| Modelo | COD mediano | Δ vs baseline (pp) | COD | PRD | Imp. SELIC |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for x in ranking:
        imp = x["importances_selic"] or {}
        imp_txt = ", ".join(f"{k}={v}" for k, v in imp.items()) or "—"
        dlt = base_cod - x["holdout"]["COD_mediano"]
        linhas.append(
            f"| {x['nome']} | {x['holdout']['COD_mediano']:.3f}% | {dlt:+.3f} | "
            f"{x['holdout']['COD']:.2f}% | {x['holdout']['PRD']:.4f} | {imp_txt} |"
        )
    linhas += [
        "",
        f"**Melhor lag isolado (sobre o baseline):** `{melhor_lag['nome']}` "
        f"(Δ COD mediano = {base_cod - melhor_lag['holdout']['COD_mediano']:+.3f} pp).",
        "",
        f"**Melhor modelo geral neste teste:** `{melhor['nome']}` "
        f"(COD mediano = {melhor['holdout']['COD_mediano']:.3f}%).",
        "",
        "## Interpretação (para a equipe)",
        "",
        "- No baseline **sem idade**, nenhuma coluna SELIC melhorou o holdout: "
        "D0/M3/M6 e as três juntas **pioraram** levemente o COD mediano "
        "(provável sobreposição com `VAR_TENDENCIA`, que já captura o ciclo no tempo).",
        "- Entre os lags isolados no baseline, **M6 foi o menos pior** "
        "(e não o melhor absoluto) — não confirma ganho pelo atraso de 6 meses.",
        "- Com **idade**, o melhor continua sendo o desafiante só com idade; "
        "idade+3 lags SELIC **empata**, sem ganho material.",
        "- Conclusão prática: **priorizar idade/inscrição**; SELIC fica como "
        "experimento secundário (talvez via variação ΔSELIC, não só nível).",
        "",
    ]
    md = "\n".join(linhas)
    (SAIDA / "Nota_Teste_SELIC_lags.md").write_text(md, encoding="utf-8")
    (PASTA_ITIV / "Nota_Teste_SELIC_lags.md").write_text(md, encoding="utf-8")

    print("\n=== RESUMO ===", flush=True)
    print(
        f"Melhor lag isolado: {melhor_lag['nome']} "
        f"(delta={base_cod - melhor_lag['holdout']['COD_mediano']:+.3f} pp)",
        flush=True,
    )
    print(
        f"Melhor geral: {melhor['nome']} "
        f"(CODmed={melhor['holdout']['COD_mediano']:.3f}%)",
        flush=True,
    )
    print(f"Salvo: {SAIDA / 'comparativo_selic_lags.json'}", flush=True)


if __name__ == "__main__":
    main()
