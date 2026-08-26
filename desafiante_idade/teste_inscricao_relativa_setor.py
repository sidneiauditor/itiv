# -*- coding: utf-8 -*-
"""Teste: inscricao relativa no setor (critica Gabriel — ritmo de cadastro).

Em vez do numero absoluto CDINSCRICAOIMOB, usa posicao do imovel dentro do
setor fiscal:

  LOG_INSCRICAO_REL = LOG_INSCRICAO - mediana(LOG_INSCRICAO | setor no treino)
  RANK_INSCRICAO_SETOR = percentil empirico da inscricao dentro do setor (0–1)

Assim, "alto no setor" ≈ estoque mais novo *naquele pedaco*, independente do
ritmo global de criacao de inscricoes ao longo dos anos.

Executar:
  python -u desafiante_idade/teste_inscricao_relativa_setor.py
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

FEATURES_REL = ["LOG_INSCRICAO_REL", "RANK_INSCRICAO_SETOR"]


def _log_insc(df: pd.DataFrame) -> pd.Series:
    insc = pd.to_numeric(df["CDINSCRICAOIMOB"], errors="coerce")
    return np.log1p(insc.clip(lower=0))


def stats_setor_treino(df_treino: pd.DataFrame) -> pd.DataFrame:
    """Mediana e distribuicao empirica de LOG_INSCRICAO por setor — so no treino."""
    tmp = df_treino.copy()
    tmp["LOG_INSCRICAO"] = _log_insc(tmp)
    tmp["CDSETORFISCAL"] = pd.to_numeric(tmp["CDSETORFISCAL"], errors="coerce")
    ok = tmp.dropna(subset=["CDSETORFISCAL", "LOG_INSCRICAO"])

    meds = []
    vals_por_setor: dict[float, np.ndarray] = {}
    for setor, g in ok.groupby("CDSETORFISCAL"):
        vals = np.sort(g["LOG_INSCRICAO"].to_numpy())
        vals_por_setor[float(setor)] = vals
        meds.append(
            {
                "CDSETORFISCAL": setor,
                "LOG_INSCRICAO_MED_SETOR": float(np.median(vals)),
                "n_setor": int(len(vals)),
            }
        )
    stats = pd.DataFrame(meds)
    stats.attrs["vals_por_setor"] = vals_por_setor
    return stats


def anexar_inscricao_relativa(
    df: pd.DataFrame,
    stats: pd.DataFrame,
) -> pd.DataFrame:
    out = df.copy()
    out["LOG_INSCRICAO"] = _log_insc(out)
    out["CDSETORFISCAL"] = pd.to_numeric(out["CDSETORFISCAL"], errors="coerce")

    med = stats.set_index("CDSETORFISCAL")["LOG_INSCRICAO_MED_SETOR"]
    out["LOG_INSCRICAO_MED_SETOR"] = out["CDSETORFISCAL"].map(med)
    # Fallback global se setor raro/ausente no treino
    med_global = float(stats["LOG_INSCRICAO_MED_SETOR"].median())
    out["LOG_INSCRICAO_MED_SETOR"] = out["LOG_INSCRICAO_MED_SETOR"].fillna(med_global)
    out["LOG_INSCRICAO_REL"] = out["LOG_INSCRICAO"] - out["LOG_INSCRICAO_MED_SETOR"]

    # Percentil empirico dentro do setor (0 = mais antigo no setor, 1 = mais novo)
    vals_map: dict[float, np.ndarray] = stats.attrs.get("vals_por_setor", {})
    ranks = []
    for setor, logi in zip(out["CDSETORFISCAL"].to_numpy(), out["LOG_INSCRICAO"].to_numpy()):
        if not np.isfinite(setor) or not np.isfinite(logi):
            ranks.append(np.nan)
            continue
        arr = vals_map.get(float(setor))
        if arr is None or len(arr) == 0:
            ranks.append(0.5)
            continue
        # fracao de inscricoes do setor <= esta (empirico)
        ranks.append(float(np.searchsorted(arr, logi, side="right") / len(arr)))
    out["RANK_INSCRICAO_SETOR"] = ranks
    return out


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

    foco_keys = FEATURES_IDADE + ["LOG_INSCRICAO"] + FEATURES_REL
    imp = {
        f: int(v)
        for f, v in zip(features, model.feature_importances_.tolist())
        if f in foco_keys
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
    print("Teste inscricao relativa no setor", flush=True)
    nasc = carregar_nascimento()
    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")

    pool = anexar_idade(pool, nasc)
    teste = anexar_idade(teste, nasc)

    pool_san = preparar_area_saneamento(pool)
    pool_limpo = aplicar_chauvenet_iterativo(pool_san).copy()
    pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)
    teste_p = teste.copy()
    teste_p["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste_p, k=K_VIZINHOS)

    # Stats de setor SO no pool limpo (sem vazamento do holdout)
    stats = stats_setor_treino(pool_limpo)
    print(f"  Setores com estatistica: {len(stats)}", flush=True)
    print(
        f"  n_setor mediana={stats['n_setor'].median():.0f} "
        f"min={stats['n_setor'].min()} max={stats['n_setor'].max()}",
        flush=True,
    )

    pool_limpo = anexar_inscricao_relativa(pool_limpo, stats)
    teste_p = anexar_inscricao_relativa(teste_p, stats)

    # Diagnostico: correlacao absoluto × relativo
    for a, b in (
        ("LOG_INSCRICAO", "LOG_INSCRICAO_REL"),
        ("LOG_INSCRICAO", "RANK_INSCRICAO_SETOR"),
        ("IDADE_NA_TRANSACAO", "LOG_INSCRICAO_REL"),
        ("IDADE_NA_TRANSACAO", "RANK_INSCRICAO_SETOR"),
    ):
        sub = pool_limpo[[a, b]].dropna()
        if len(sub) > 100:
            print(f"  corr({a},{b})={sub.corr().iloc[0,1]:.3f}", flush=True)

    base = list(FEATURES_LGBM)
    idade = FEATURES_IDADE
    absoluto = ["LOG_INSCRICAO"]

    variantes = [
        ("baseline", base),
        ("so_inscricao_abs", base + absoluto),
        ("so_inscricao_rel", base + FEATURES_REL),
        ("abs_mais_rel", base + absoluto + FEATURES_REL),
        ("idade_mais_abs", base + idade + absoluto),
        ("idade_mais_rel", base + idade + FEATURES_REL),
        ("idade_abs_rel", base + idade + absoluto + FEATURES_REL),
    ]

    resultados = []
    preds = {"SQTRANSMISSAO": teste_p["SQTRANSMISSAO"].to_numpy()}
    for nome, feats in variantes:
        r = treinar(pool_limpo, teste_p, feats, nome)
        preds[f"PRED_{nome}"] = r["pred"]
        del r["pred"]
        resultados.append(r)

    ranking = sorted(resultados, key=lambda x: x["holdout"]["COD_mediano"])
    base_cod = next(x["holdout"]["COD_mediano"] for x in resultados if x["nome"] == "baseline")
    antigo_base = next(
        x["por_inscricao"]["<300k"]["COD_mediano"]
        for x in resultados if x["nome"] == "baseline"
    )

    resumo = {
        "definicao": {
            "LOG_INSCRICAO": "log1p(CDINSCRICAOIMOB) — absoluto",
            "LOG_INSCRICAO_REL": "LOG_INSCRICAO - mediana(LOG_INSCRICAO|setor) no treino",
            "RANK_INSCRICAO_SETOR": "percentil empirico da inscricao dentro do setor (0–1)",
            "stats_setor": "calculadas apenas no pool de treino (sem vazamento)",
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

    out_json = SAIDA / "comparativo_inscricao_relativa_setor.json"
    out_json.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(preds).to_csv(SAIDA / "preds_inscricao_relativa_setor.csv", index=False)

    linhas = [
        "# Inscricao relativa no setor (critica Gabriel — ritmo de cadastro)",
        "",
        "- `LOG_INSCRICAO_REL` = log(inscricao) − mediana do setor (treino)",
        "- `RANK_INSCRICAO_SETOR` = percentil da inscricao dentro do setor (0=antigo, 1=novo)",
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
        "- Se **so_inscricao_rel** ≈ ou > **so_inscricao_abs**: a forma relativa "
        "responde à crítica do ritmo sem perder sinal.",
        "- Se absoluto ganha: o número bruto ainda carrega informação de época "
        "da cidade (não só posição local).",
        "- Se **idade_abs_rel** ganha pouco sobre **idade_mais_abs**: relativo é "
        "refinamento, não troca de estratégia.",
        "",
        f"Arquivos: `{out_json.name}`, `preds_inscricao_relativa_setor.csv`.",
    ]
    nota = "\n".join(linhas) + "\n"
    (SAIDA / "Nota_Inscricao_Relativa_Setor.md").write_text(nota, encoding="utf-8")
    (PASTA_ITIV / "Nota_Inscricao_Relativa_Setor.md").write_text(nota, encoding="utf-8")

    print("\n=== RESUMO ===", flush=True)
    for r in ranking:
        ant = (r["por_inscricao"].get("<300k") or {}).get("COD_mediano")
        msg = f"  {r['nome']}: CODmed={r['holdout']['COD_mediano']:.3f}%"
        if ant is not None:
            msg += f" | antigos={ant:.2f}%"
        print(msg, flush=True)
    print(f"JSON: {out_json}", flush=True)


if __name__ == "__main__":
    main()
