# -*- coding: utf-8 -*-
"""Teste KNN com similaridade de idade/inscricao.

KNN atual (aprovado): k vizinhos so por (X, Y) → media log(R$/m2).
Variantes:
  - KNN_GEO: igual ao aprovado
  - KNN_INSC: distancia em (X, Y, LOG_INSCRICAO) padronizados
  - KNN_IDADE: distancia em (X, Y, IDADE_IMP) padronizados
  - KNN_GEO + KNN_INSC: as duas features juntas

Executar:
  python -u desafiante_idade/teste_knn_idade.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

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

PARAMS = {
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "n_estimators": 800,
    "num_leaves": 63,
    "random_state": SEMENTE,
    "verbosity": -1,
}


def anexar_log_inscricao(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    insc = pd.to_numeric(out["CDINSCRICAOIMOB"], errors="coerce")
    out["LOG_INSCRICAO"] = np.log1p(insc.clip(lower=0))
    return out


def calcular_knn_composto(
    df_base: pd.DataFrame,
    df_alvo: pd.DataFrame,
    cols: list[str],
    k: int = K_VIZINHOS,
) -> np.ndarray:
    """KNN em espaco padronizado das colunas `cols`; media do log(R$/m2) dos vizinhos.

    Padronizacao usa media/desvio da BASE (treino) — sem vazamento do alvo.
    """
    base = df_base.copy()
    m2 = base["VLTRANSACAO_DEFLACIONADO"] / np.exp(base["LOG_AREA"])
    base["_LOGM2"] = np.log(m2.where(m2 > 0))

    need = cols + ["_LOGM2"]
    base_ok = base.dropna(subset=need).copy()
    proxy = np.full(len(df_alvo), np.nan)
    if len(base_ok) < k + 1:
        return proxy

    mu = base_ok[cols].mean()
    sd = base_ok[cols].std().replace(0, 1.0)
    Xb = ((base_ok[cols] - mu) / sd).to_numpy()

    mesmo = df_alvo is df_base
    kk = k + 1 if mesmo else k
    nn = NearestNeighbors(n_neighbors=min(kk, len(base_ok))).fit(Xb)

    alvo = df_alvo.copy()
    for c in cols:
        if c not in alvo.columns:
            alvo[c] = np.nan
    validos = alvo[cols].notna().all(axis=1).to_numpy()
    if validos.sum() == 0:
        return proxy

    Xa = ((alvo.loc[validos, cols] - mu) / sd).to_numpy()
    _, idx = nn.kneighbors(Xa)
    logm2 = base_ok["_LOGM2"].to_numpy()
    vals = []
    for linha in idx:
        v = logm2[linha]
        if mesmo:
            v = v[1:]
        vals.append(float(np.nanmean(v)))
    proxy[validos] = vals
    return proxy


def _montar(df, features, fill):
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


def _metricas_faixa(pred, real, mascara):
    m = mascara & (real > 0) & np.isfinite(pred) & np.isfinite(real)
    if m.sum() < 30:
        return {"n": int(m.sum()), "COD_mediano": None, "COD": None, "PRD": None}
    met = metricas_completas(pred[m], real[m])
    return {
        "n": int(m.sum()),
        "COD_mediano": float(met["COD_mediano"]),
        "COD": float(met["COD"]),
        "PRD": float(met["PRD"]),
    }


def treinar(treino, teste, features, nome):
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
    print(
        f"  holdout CODmed={met['COD_mediano']:.3f}% COD={met['COD']:.3f}% "
        f"PRD={met['PRD']:.4f}",
        flush=True,
    )

    estrat = {}
    insc = pd.to_numeric(teste["CDINSCRICAOIMOB"], errors="coerce").to_numpy()
    for nome_fx, lo, hi in FAIXAS_INSCRICAO:
        estrat[nome_fx] = _metricas_faixa(pred, real, (insc >= lo) & (insc < hi))
        cm = estrat[nome_fx].get("COD_mediano")
        if cm is not None:
            print(f"    {nome_fx}: CODmed={cm:.2f}% n={estrat[nome_fx]['n']}", flush=True)

    knn_cols = [c for c in features if c.startswith("KNN_")]
    imp = {
        f: int(v)
        for f, v in zip(features, model.feature_importances_.tolist())
        if f in knn_cols or f in FEATURES_IDADE or f == "LOG_INSCRICAO"
    }
    if imp:
        print(f"  importancia foco: {imp}", flush=True)

    return {
        "nome": nome,
        "features": features,
        "holdout": {k: float(v) for k, v in met.items()},
        "por_inscricao": estrat,
        "importances_foco": imp,
        "pred": pred,
    }


def main():
    print("Teste KNN geografico × KNN com idade/inscricao", flush=True)
    nasc = carregar_nascimento()
    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")

    pool = anexar_log_inscricao(anexar_idade(pool, nasc))
    teste = anexar_log_inscricao(anexar_idade(teste, nasc))

    pool_san = preparar_area_saneamento(pool)
    pool_limpo = aplicar_chauvenet_iterativo(pool_san).copy()
    teste_p = teste.copy()

    # --- proxies KNN ---
    print("Calculando KNN_GEO (aprovado)...", flush=True)
    pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)
    teste_p["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste_p, k=K_VIZINHOS)

    print("Calculando KNN_INSC (X,Y + log inscricao)...", flush=True)
    cols_insc = ["VLCOORDGEOX", "VLCOORDGEOY", "LOG_INSCRICAO"]
    pool_limpo["KNN_INSC"] = calcular_knn_composto(pool_limpo, pool_limpo, cols_insc)
    teste_p["KNN_INSC"] = calcular_knn_composto(pool_limpo, teste_p, cols_insc)

    print("Calculando KNN_IDADE (X,Y + idade imputada)...", flush=True)
    cols_idade = ["VLCOORDGEOX", "VLCOORDGEOY", "IDADE_NA_TRANSACAO_IMP"]
    pool_limpo["KNN_IDADE"] = calcular_knn_composto(pool_limpo, pool_limpo, cols_idade)
    teste_p["KNN_IDADE"] = calcular_knn_composto(pool_limpo, teste_p, cols_idade)

    # Correlacao entre proxies (diagnostico)
    for a, b in (("KNN_PROXY", "KNN_INSC"), ("KNN_PROXY", "KNN_IDADE"), ("KNN_INSC", "KNN_IDADE")):
        c = pool_limpo[[a, b]].dropna().corr().iloc[0, 1]
        print(f"  corr({a},{b})={c:.3f}", flush=True)

    base_feats = [f for f in FEATURES_LGBM if f != "KNN_PROXY"]
    idade_insc = FEATURES_IDADE + ["LOG_INSCRICAO"]

    variantes = [
        ("baseline_knn_geo", base_feats + ["KNN_PROXY"]),
        ("baseline_knn_insc", base_feats + ["KNN_INSC"]),
        ("baseline_knn_idade", base_feats + ["KNN_IDADE"]),
        ("baseline_knn_geo_mais_insc", base_feats + ["KNN_PROXY", "KNN_INSC"]),
        ("idade_insc_knn_geo", base_feats + ["KNN_PROXY"] + idade_insc),
        ("idade_insc_knn_insc", base_feats + ["KNN_INSC"] + idade_insc),
        ("idade_insc_knn_geo_mais_insc", base_feats + ["KNN_PROXY", "KNN_INSC"] + idade_insc),
    ]

    resultados = []
    preds = {"SQTRANSMISSAO": teste_p["SQTRANSMISSAO"].to_numpy()}
    for nome, feats in variantes:
        r = treinar(pool_limpo, teste_p, feats, nome)
        preds[f"PRED_{nome}"] = r["pred"]
        del r["pred"]
        resultados.append(r)

    ranking = sorted(resultados, key=lambda x: x["holdout"]["COD_mediano"])
    base_cod = next(
        x["holdout"]["COD_mediano"] for x in resultados if x["nome"] == "baseline_knn_geo"
    )
    antigo_base = next(
        x["por_inscricao"]["<300k"]["COD_mediano"]
        for x in resultados if x["nome"] == "baseline_knn_geo"
    )

    resumo = {
        "definicao": {
            "KNN_PROXY": "k vizinhos so por (X,Y) — aprovado",
            "KNN_INSC": "k vizinhos por (X,Y,LOG_INSCRICAO) padronizados",
            "KNN_IDADE": "k vizinhos por (X,Y,IDADE_NA_TRANSACAO_IMP) padronizados",
            "k": K_VIZINHOS,
        },
        "baseline_cod_mediano": float(base_cod),
        "baseline_cod_mediano_antigos": float(antigo_base),
        "melhor_modelo": ranking[0]["nome"],
        "ranking_cod_mediano": [
            {
                "nome": r["nome"],
                "COD_mediano": r["holdout"]["COD_mediano"],
                "COD": r["holdout"]["COD"],
                "PRD": r["holdout"]["PRD"],
                "delta_vs_baseline_pp": base_cod - r["holdout"]["COD_mediano"],
                "COD_mediano_antigos_<300k": (r["por_inscricao"].get("<300k") or {}).get(
                    "COD_mediano"
                ),
                "delta_antigos_pp": (
                    antigo_base - (r["por_inscricao"].get("<300k") or {}).get("COD_mediano")
                    if (r["por_inscricao"].get("<300k") or {}).get("COD_mediano") is not None
                    else None
                ),
                "por_inscricao": r["por_inscricao"],
                "importances_foco": r["importances_foco"],
            }
            for r in ranking
        ],
        "modelos": resultados,
    }

    out_json = SAIDA / "comparativo_knn_idade.json"
    out_json.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(preds).to_csv(SAIDA / "preds_knn_idade.csv", index=False)

    linhas = [
        "# Teste KNN geografico × KNN com idade/inscricao",
        "",
        "O `KNN_PROXY` aprovado busca os k vizinhos **só por coordenadas** e usa a média do log(R$/m²).",
        "Aqui testamos vizinhos que também sejam parecidos em **inscrição** ou **idade**.",
        "",
        "| Modelo | COD mediano | Δ vs baseline | COD antigos (<300k) | Δ antigos |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in ranking:
        ant = (r["por_inscricao"].get("<300k") or {}).get("COD_mediano")
        d_ant = (antigo_base - ant) if ant is not None else None
        linhas.append(
            f"| {r['nome']} | {r['holdout']['COD_mediano']:.3f}% | "
            f"{base_cod - r['holdout']['COD_mediano']:+.3f} | "
            f"{(f'{ant:.2f}%' if ant is not None else '—')} | "
            f"{(f'{d_ant:+.2f}' if d_ant is not None else '—')} |"
        )
    linhas += [
        "",
        f"**Melhor global:** `{ranking[0]['nome']}`.",
        "",
        "## Interpretação",
        "",
        "- Se KNN_INSC/KNN_IDADE melhorar sobretudo os **antigos**, a sacada funciona: "
        "vizinho geográfico novo não deve ancorar preço de imóvel antigo.",
        "- Se empatar com idade+inscrição já no LightGBM, o KNN composto é redundante.",
        "",
        f"Arquivos: `{out_json.name}`, `preds_knn_idade.csv`.",
    ]
    nota = "\n".join(linhas) + "\n"
    (SAIDA / "Nota_Teste_KNN_Idade.md").write_text(nota, encoding="utf-8")
    (PASTA_ITIV / "Nota_Teste_KNN_Idade.md").write_text(nota, encoding="utf-8")

    print("\n=== RESUMO ===", flush=True)
    for r in ranking:
        ant = (r["por_inscricao"].get("<300k") or {}).get("COD_mediano")
        print(
            f"  {r['nome']}: CODmed={r['holdout']['COD_mediano']:.3f}% "
            f"| antigos={ant:.2f}%" if ant is not None else
            f"  {r['nome']}: CODmed={r['holdout']['COD_mediano']:.3f}%",
            flush=True,
        )
    print(f"JSON: {out_json}", flush=True)


if __name__ == "__main__":
    main()
