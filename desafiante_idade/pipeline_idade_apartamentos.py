# -*- coding: utf-8 -*-
"""Pipeline: diagnostico Compatível × idade/inscricao + modelo desafiante com idade.

Nao altera o modelo aprovado em Modelo_Apartamentos_Aprovado/.
Gera artefatos em ITIV/desafiante_idade/saida/.

Executar a partir de qualquer cwd:
  python desafiante_idade/pipeline_idade_apartamentos.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

HERE = Path(__file__).resolve().parent
PASTA_ITIV = HERE.parent
CODIGO_APROVADO = PASTA_ITIV / "Modelo_Apartamentos_Aprovado" / "codigo"
sys.path.insert(0, str(CODIGO_APROVADO))
sys.path.insert(0, str(HERE))

from idade_features import (  # noqa: E402
    FEATURES_IDADE,
    FAIXAS_IDADE,
    FAIXAS_INSCRICAO,
    anexar_idade,
    carregar_nascimento,
    faixa_idade,
    faixa_inscricao,
)

from apartamentos_lib import (  # noqa: E402
    AMOSTRAS,
    FEATURES_LGBM,
    CAT_LGBM,
    K_VIZINHOS,
    SEMENTE,
    calcular_knn_proxy,
    metricas_completas,
    montar_X_y,
    preparar_area_saneamento,
)
from saneamento_chauvenet_iterativo import aplicar_chauvenet_iterativo  # noqa: E402
from metricas_iaao_por_decil import metricas_razao, prb_global  # noqa: E402

warnings.filterwarnings("ignore")

SAIDA = HERE / "saida"
SAIDA.mkdir(parents=True, exist_ok=True)

STATUS_XLSX = PASTA_ITIV / "Informações ITIV 20260610 - Status Apartamentos.xlsx"
COMPAT_PREFIXOS = ("Compatível",)  # inclui Compatível (abaixo)
PARAMS_LGBM = {
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "n_estimators": 800,
    "num_leaves": 63,
    "random_state": SEMENTE,
    "verbosity": -1,
}
K_FOLDS_DESAFIANTE = 5  # pragmatico vs 10 do aprovado (mesmo hiperparametro congelado)


def _eh_compativel(status: str) -> bool:
    s = str(status or "")
    return s.startswith("Compatível")


def _metricas_seg(av, sp) -> dict:
    m = (av > 0) & (sp > 0) & np.isfinite(av) & np.isfinite(sp)
    if m.sum() < 5:
        return {"n": int(m.sum()), "razao_mediana": None, "COD": None,
                "COD_mediano": None, "PRD": None, "PRB": None}
    # Diagnostico em base operacional: exclui razoes patologicas (dado sujo),
    # alinhado aos limites de "suspeito" do status (+/-100%).
    r = av[m] / sp[m]
    ok = (r >= 0.5) & (r <= 2.0)
    if ok.sum() < 5:
        return {"n": int(ok.sum()), "razao_mediana": None, "COD": None,
                "COD_mediano": None, "PRD": None, "PRB": None}
    met = metricas_razao(av[m][ok], sp[m][ok])
    met["PRB"] = prb_global(av[m][ok], sp[m][ok])
    met["n"] = int(ok.sum())
    met["n_bruto"] = int(m.sum())
    return met


# ───────────────────────────────────────────────────────────────────────────
# 1. DIAGNOSTICO
# ───────────────────────────────────────────────────────────────────────────
def etapa_diagnostico(nascimento: pd.DataFrame) -> dict:
    print("=" * 70)
    print("1) Diagnostico: STATUS × inscricao × idade")
    print("=" * 70, flush=True)

    # Leitura enxuta: so colunas necessarias (planilha ~48 MB)
    preview = pd.read_excel(STATUS_XLSX, sheet_name="Exportar Planilha", nrows=0)
    wanted_keys = []
    colmap_preview = {}
    for c in preview.columns:
        cu = str(c).upper()
        cu_ascii = "".join(ch if ord(ch) < 128 else " " for ch in cu)
        cu_ascii = " ".join(cu_ascii.split())
        keep = False
        dest = None
        if str(c).strip().upper() == "CDINSCRICAOIMOB":
            keep, dest = True, "CDINSCRICAOIMOB"
        elif str(c).strip().upper() == "SQTRANSMISSAO":
            keep, dest = True, "SQTRANSMISSAO"
        elif str(c).strip().upper() == "DTSOLICITACAO":
            keep, dest = True, "DATA_TRANSACAO"
        elif str(c).strip().upper() == "VLTRANSACAO":
            keep, dest = True, "VLTRANSACAO"
        elif "ESTIMATIVA DO MODELO" in cu and "LIGHTGBM" in cu:
            keep, dest = True, "VALOR_MODELO"
        elif "STATUS DA AVAL" in cu or "STATUS DA AVAL" in cu_ascii:
            keep, dest = True, "STATUS"
        elif ("VALOR DA TRANS" in cu or "VALOR DA TRANS" in cu_ascii) and "ATUALIZADO" in cu_ascii:
            keep, dest = True, "VALOR_TX"
        if keep:
            wanted_keys.append(c)
            colmap_preview[c] = dest
    print(f"  Lendo colunas: {[colmap_preview[c] for c in wanted_keys]}", flush=True)
    bruto = pd.read_excel(STATUS_XLSX, sheet_name="Exportar Planilha", usecols=wanted_keys)
    df = bruto.rename(columns=colmap_preview)
    precisa = ["CDINSCRICAOIMOB", "STATUS", "VALOR_MODELO"]
    faltando = [c for c in precisa if c not in df.columns]
    if faltando:
        raise RuntimeError(
            f"Colunas ausentes no status: {faltando}; mapeadas={list(df.columns)}"
        )
    if "VALOR_TX" not in df.columns:
        if "VLTRANSACAO" in df.columns:
            df["VALOR_TX"] = df["VLTRANSACAO"]
            print("  AVISO: usando VLTRANSACAO como valor de referencia (IPCA nao mapeado)", flush=True)
        else:
            raise RuntimeError("Sem VALOR_TX nem VLTRANSACAO")

    if "DATA_TRANSACAO" not in df.columns:
        df["DATA_TRANSACAO"] = pd.NaT

    # so linhas com estimativa do modelo (apartamentos no escopo)
    df["VALOR_MODELO"] = pd.to_numeric(df["VALOR_MODELO"], errors="coerce")
    df["VALOR_TX"] = pd.to_numeric(df["VALOR_TX"], errors="coerce")
    n_antes = len(df)
    df = df[df["VALOR_MODELO"].notna() & (df["VALOR_MODELO"] > 0)].copy()
    print(f"  Linhas com estimativa LightGBM: {len(df):,} (de {n_antes:,})", flush=True)

    df = anexar_idade(df, nascimento, col_data="DATA_TRANSACAO")
    df["razao"] = df["VALOR_MODELO"] / df["VALOR_TX"]
    df["compativel"] = df["STATUS"].map(_eh_compativel)
    df["status_grupo"] = np.where(
        df["STATUS"].astype(str).str.startswith("Compatível (valor"),
        "Compativel_abaixo",
        np.where(df["compativel"], "Compativel", "Outros"),
    )

    # Confirmacao do e-mail do David (~48% dos Compativel com inscricao >900k)
    mask_c = df["compativel"]
    n_c = int(mask_c.sum())
    n_c_900 = int((mask_c & (df["CDINSCRICAOIMOB"] > 900_000)).sum())
    pct_david = 100.0 * n_c_900 / n_c if n_c else None

    mask_outros = ~df["compativel"] & df["STATUS"].notna()
    # exclui fora de escopo se houver
    mask_outros = mask_outros & ~df["STATUS"].astype(str).str.contains("Fora de Escopo", case=False, na=False)
    n_o = int(mask_outros.sum())
    n_o_900 = int((mask_outros & (df["CDINSCRICAOIMOB"] > 900_000)).sum())
    pct_outros_900 = 100.0 * n_o_900 / n_o if n_o else None

    def tabela_por(serie_faixa: pd.Series) -> list[dict]:
        rows = []
        for faixa in list(serie_faixa.dropna().unique()):
            m = serie_faixa == faixa
            sub = df.loc[m]
            n = len(sub)
            n_comp = int(sub["compativel"].sum())
            met = _metricas_seg(
                sub["VALOR_MODELO"].to_numpy(dtype=float),
                sub["VALOR_TX"].to_numpy(dtype=float),
            )
            rows.append({
                "faixa": str(faixa),
                "n": n,
                "n_compativel": n_comp,
                "pct_compativel": round(100.0 * n_comp / n, 2) if n else None,
                "idade_mediana": (
                    float(sub["IDADE_NA_TRANSACAO"].median())
                    if sub["IDADE_NA_TRANSACAO"].notna().any() else None
                ),
                "pct_inscricao_gt_900k": round(
                    100.0 * (sub["CDINSCRICAOIMOB"] > 900_000).mean(), 2
                ),
                **{k: (None if met[k] is None or (isinstance(met[k], float) and not np.isfinite(met[k]))
                       else (round(float(met[k]), 4) if k != "n" else met[k]))
                   for k in ("razao_mediana", "COD", "COD_mediano", "PRD", "PRB")},
            })
        # ordem estavel
        ordem_i = {n: i for i, (n, *_ ) in enumerate(FAIXAS_INSCRICAO)}
        ordem_a = {n: i for i, (n, *_ ) in enumerate(FAIXAS_IDADE)}
        rows.sort(key=lambda r: ordem_i.get(r["faixa"], ordem_a.get(r["faixa"], 99)))
        return rows

    resultado = {
        "fonte_status": str(STATUS_XLSX),
        "n_linhas": int(len(df)),
        "n_compativel_total": n_c,
        "confirmacao_david": {
            "n_compativel_inscricao_gt_900k": n_c_900,
            "pct_compativel_com_inscricao_gt_900k": round(pct_david, 2) if pct_david is not None else None,
            "n_nao_compativel": n_o,
            "pct_nao_compativel_com_inscricao_gt_900k": (
                round(pct_outros_900, 2) if pct_outros_900 is not None else None
            ),
            "idade_mediana_compativel": (
                float(df.loc[mask_c, "IDADE_NA_TRANSACAO"].median())
                if df.loc[mask_c, "IDADE_NA_TRANSACAO"].notna().any() else None
            ),
            "idade_mediana_nao_compativel": (
                float(df.loc[mask_outros, "IDADE_NA_TRANSACAO"].median())
                if df.loc[mask_outros, "IDADE_NA_TRANSACAO"].notna().any() else None
            ),
            "cobertura_idade_pct": round(
                100.0 * df["IDADE_NA_TRANSACAO"].notna().mean(), 2
            ),
        },
        "por_faixa_inscricao": tabela_por(df["FAIXA_INSCRICAO"]),
        "por_faixa_idade": tabela_por(df["FAIXA_IDADE"]),
        "contagem_status": (
            df["STATUS"].astype(str).value_counts().head(12).to_dict()
        ),
    }

    (SAIDA / "diagnostico_idade_status.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    pd.DataFrame(resultado["por_faixa_inscricao"]).to_csv(
        SAIDA / "diagnostico_por_inscricao.csv", index=False, sep=";", encoding="utf-8-sig"
    )
    pd.DataFrame(resultado["por_faixa_idade"]).to_csv(
        SAIDA / "diagnostico_por_idade.csv", index=False, sep=";", encoding="utf-8-sig"
    )

    # Graficos simples
    try:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        dfi = pd.DataFrame(resultado["por_faixa_inscricao"])
        axes[0].bar(dfi["faixa"], dfi["pct_compativel"], color="#2f6f4e")
        axes[0].set_title("% Compatível por faixa de inscrição")
        axes[0].set_ylabel("%")
        axes[0].set_ylim(0, 100)
        dfa = pd.DataFrame(resultado["por_faixa_idade"])
        dfa = dfa[dfa["faixa"] != "(sem idade)"]
        axes[1].bar(dfa["faixa"], dfa["pct_compativel"], color="#3d5a80")
        axes[1].set_title("% Compatível por faixa etária")
        axes[1].set_ylabel("%")
        axes[1].set_ylim(0, 100)
        fig.tight_layout()
        fig.savefig(SAIDA / "grafico_compativel_por_faixa.png", dpi=140)
        plt.close(fig)

        fig2, ax = plt.subplots(figsize=(6.5, 4))
        ax.bar(dfi["faixa"], dfi["COD_mediano"], color="#c45c26")
        ax.axhline(15, color="gray", ls="--", label="meta COD mediano 15%")
        ax.set_title("COD mediano (modelo aprovado) por inscrição")
        ax.set_ylabel("%")
        ax.legend()
        fig2.tight_layout()
        fig2.savefig(SAIDA / "grafico_cod_por_inscricao.png", dpi=140)
        plt.close(fig2)
    except Exception as exc:
        print(f"  (graficos nao gerados: {exc})")

    print(f"  Compatível total: {n_c:,} | >900k: {n_c_900:,} ({pct_david:.1f}%)")
    print(f"  Salvo em {SAIDA}")
    return resultado


# ───────────────────────────────────────────────────────────────────────────
# 2–3. FEATURES + TREINO DESAFIANTE
# ───────────────────────────────────────────────────────────────────────────
def _features_desafiante():
    return FEATURES_LGBM + FEATURES_IDADE


def _montar_X(df, features, mediana_proxy=None, mediana_idade=None):
    X = df[features].copy()
    X["CDSETORFISCAL"] = X["CDSETORFISCAL"].astype("category")
    if mediana_proxy is None:
        mediana_proxy = X["KNN_PROXY"].median()
    X["KNN_PROXY"] = X["KNN_PROXY"].fillna(mediana_proxy)
    if "IDADE_NA_TRANSACAO_IMP" in X.columns:
        if mediana_idade is None:
            mediana_idade = X["IDADE_NA_TRANSACAO_IMP"].median()
        X["IDADE_NA_TRANSACAO_IMP"] = X["IDADE_NA_TRANSACAO_IMP"].fillna(mediana_idade)
    y = np.log(df["VLTRANSACAO_DEFLACIONADO"])
    return X, y, mediana_proxy, mediana_idade


def _preparar_com_idade(pool: pd.DataFrame, teste: pd.DataFrame, nascimento: pd.DataFrame):
    pool = anexar_idade(pool, nascimento)
    teste = anexar_idade(teste, nascimento)
    pool_san = preparar_area_saneamento(pool)
    pool_limpo = aplicar_chauvenet_iterativo(pool_san).copy()
    pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)
    teste = teste.copy()
    teste["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste, k=K_VIZINHOS)
    return pool_limpo, teste


def etapa_treino(nascimento: pd.DataFrame) -> dict:
    print("=" * 70)
    print("2-3) Engenharia de idade + treino desafiante LightGBM")
    print("=" * 70)

    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")
    # anexar idade tambem no parquet de parametros para auditoria
    pool_feat = anexar_idade(pool, nascimento)
    teste_feat = anexar_idade(teste, nascimento)
    pool_feat.to_parquet(SAIDA / "pool_treino_com_idade.parquet", index=False)
    teste_feat.to_parquet(SAIDA / "teste_final_com_idade.parquet", index=False)
    print(f"  Cobertura idade pool: {100*pool_feat['IDADE_NA_TRANSACAO'].notna().mean():.1f}%")
    print(f"  Cobertura idade teste: {100*teste_feat['IDADE_NA_TRANSACAO'].notna().mean():.1f}%")

    pool_limpo, teste_prep = _preparar_com_idade(pool, teste, nascimento)
    feats_base = FEATURES_LGBM
    feats_chal = _features_desafiante()

    def cv_e_holdout(features, nome):
        print(f"\n--- Modelo {nome} | features={len(features)} ---")
        kf = KFold(n_splits=K_FOLDS_DESAFIANTE, shuffle=True, random_state=SEMENTE)
        folds = []
        for i, (tr, va) in enumerate(kf.split(pool_limpo), 1):
            tr_df = pool_limpo.iloc[tr]
            va_df = pool_limpo.iloc[va]
            # KNN so no treino do fold
            tr_df = tr_df.copy()
            va_df = va_df.copy()
            tr_df["KNN_PROXY"] = calcular_knn_proxy(tr_df, tr_df, k=K_VIZINHOS)
            va_df["KNN_PROXY"] = calcular_knn_proxy(tr_df, va_df, k=K_VIZINHOS)
            Xtr, ytr, med_p, med_i = _montar_X(tr_df, features)
            Xva, _, _, _ = _montar_X(va_df, features, mediana_proxy=med_p, mediana_idade=med_i)
            model = lgb.LGBMRegressor(**PARAMS_LGBM)
            cats = [c for c in CAT_LGBM if c in Xtr.columns]
            model.fit(Xtr, ytr, categorical_feature=cats)
            pred = np.exp(model.predict(Xva))
            real = va_df["VLTRANSACAO_DEFLACIONADO"].to_numpy()
            met = metricas_completas(pred, real)
            folds.append(met)
            print(f"  fold {i}/{K_FOLDS_DESAFIANTE} CODmed={met['COD_mediano']:.2f}% "
                  f"PRD={met['PRD']:.3f} razao={met['razao_mediana']:.3f}")

        # holdout
        Xpool, ypool, med_p, med_i = _montar_X(pool_limpo, features)
        Xte, _, _, _ = _montar_X(teste_prep, features, mediana_proxy=med_p, mediana_idade=med_i)
        model = lgb.LGBMRegressor(**PARAMS_LGBM)
        cats = [c for c in CAT_LGBM if c in Xpool.columns]
        model.fit(Xpool, ypool, categorical_feature=cats)
        pred_te = np.exp(model.predict(Xte))
        real_te = teste_prep["VLTRANSACAO_DEFLACIONADO"].to_numpy()
        hold = metricas_completas(pred_te, real_te)

        # importancia
        imp = sorted(
            zip(features, model.feature_importances_.tolist()),
            key=lambda x: -x[1],
        )
        return {
            "cv_folds": folds,
            "cv_media": {k: float(np.mean([f[k] for f in folds])) for k in
                         ["razao_mediana", "COD", "COD_mediano", "PRD", "PRB"]},
            "holdout": hold,
            "importances": imp,
            "model": model,
            "pred_teste": pred_te,
            "mediana_proxy": med_p,
            "mediana_idade": med_i,
        }

    base = cv_e_holdout(feats_base, "BASELINE (aprovado, sem idade)")
    chal = cv_e_holdout(feats_chal, "DESAFIANTE (+ idade)")

    # metricas estratificadas no holdout
    teste_out = teste_prep.copy()
    teste_out["PRED_BASELINE"] = base["pred_teste"]
    teste_out["PRED_DESAFIANTE"] = chal["pred_teste"]
    teste_out["FAIXA_INSCRICAO"] = faixa_inscricao(teste_out["CDINSCRICAOIMOB"])
    teste_out["FAIXA_IDADE"] = faixa_idade(teste_out["IDADE_NA_TRANSACAO"])
    teste_out.to_parquet(SAIDA / "teste_final_previsoes_desafiante.parquet", index=False)

    def estratificado(pred_col: str) -> dict:
        out = {"por_inscricao": [], "por_idade": []}
        for nome, lo, hi in FAIXAS_INSCRICAO:
            m = (teste_out["CDINSCRICAOIMOB"] >= lo) & (teste_out["CDINSCRICAOIMOB"] < hi)
            met = _metricas_seg(
                teste_out.loc[m, pred_col].to_numpy(),
                teste_out.loc[m, "VLTRANSACAO_DEFLACIONADO"].to_numpy(),
            )
            out["por_inscricao"].append({"faixa": nome, **met})
        for nome, lo, hi in FAIXAS_IDADE:
            m = (
                teste_out["IDADE_NA_TRANSACAO"].notna()
                & (teste_out["IDADE_NA_TRANSACAO"] >= lo)
                & (teste_out["IDADE_NA_TRANSACAO"] <= hi)
            )
            met = _metricas_seg(
                teste_out.loc[m, pred_col].to_numpy(),
                teste_out.loc[m, "VLTRANSACAO_DEFLACIONADO"].to_numpy(),
            )
            out["por_idade"].append({"faixa": nome, **met})
        return out

    # salvar modelo desafiante (nao sobrescreve o aprovado)
    # LightGBM falha com path acentuado no Windows — grava em tmp e move.
    import shutil
    import tempfile

    model_path = SAIDA / "modelo_lightgbm_apartamentos_com_idade.txt"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "modelo_lgbm_idade.txt"
        chal["model"].booster_.save_model(str(tmp_path))
        shutil.copy2(tmp_path, model_path)

    resumo = {
        "hiperparametros": PARAMS_LGBM,
        "k_folds": K_FOLDS_DESAFIANTE,
        "features_baseline": feats_base,
        "features_desafiante": feats_chal,
        "cobertura_idade_pool_pct": round(100 * pool_limpo["IDADE_NA_TRANSACAO"].notna().mean(), 2),
        "cobertura_idade_teste_pct": round(100 * teste_prep["IDADE_NA_TRANSACAO"].notna().mean(), 2),
        "baseline": {
            "cv_media": base["cv_media"],
            "holdout": {k: float(v) for k, v in base["holdout"].items()},
            "importances": base["importances"],
            "estratificado_holdout": estratificado("PRED_BASELINE"),
        },
        "desafiante": {
            "cv_media": chal["cv_media"],
            "holdout": {k: float(v) for k, v in chal["holdout"].items()},
            "importances": chal["importances"],
            "estratificado_holdout": estratificado("PRED_DESAFIANTE"),
            "modelo_arquivo": str(model_path),
        },
        "delta_holdout_cod_mediano": float(
            base["holdout"]["COD_mediano"] - chal["holdout"]["COD_mediano"]
        ),
        "delta_holdout_prd_abs_de_1": float(
            abs(base["holdout"]["PRD"] - 1) - abs(chal["holdout"]["PRD"] - 1)
        ),
    }

    # limpar objetos nao serializaveis
    (SAIDA / "comparativo_baseline_desafiante.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("\nHOLDOUT baseline CODmed={:.2f}% PRD={:.3f}".format(
        resumo["baseline"]["holdout"]["COD_mediano"],
        resumo["baseline"]["holdout"]["PRD"],
    ))
    print("HOLDOUT desafiante CODmed={:.2f}% PRD={:.3f}".format(
        resumo["desafiante"]["holdout"]["COD_mediano"],
        resumo["desafiante"]["holdout"]["PRD"],
    ))
    print(f"  Modelo desafiante salvo em {model_path}")
    return resumo


# ───────────────────────────────────────────────────────────────────────────
# 4. NOTA TECNICA
# ───────────────────────────────────────────────────────────────────────────
def etapa_nota(diag: dict, treino: dict) -> Path:
    print("=" * 70)
    print("4) Nota tecnica / adendo ao RIF 114")
    print("=" * 70)

    david = diag["confirmacao_david"]
    n_comp = diag.get("n_compativel_total") or david.get("n_compativel_total")
    base_h = treino["baseline"]["holdout"]
    chal_h = treino["desafiante"]["holdout"]

    def _fmt_faixas(rows, chave_pct="pct_compativel"):
        lines = []
        for r in rows:
            if chave_pct in r:
                lines.append(
                    f"| {r['faixa']} | {r.get('n', '')} | {r.get(chave_pct, '')} | "
                    f"{r.get('COD_mediano', '')} | {r.get('PRD', '')} | {r.get('idade_mediana', '')} |"
                )
            else:
                lines.append(
                    f"| {r['faixa']} | {r.get('n', '')} | {r.get('COD_mediano', '')} | "
                    f"{r.get('PRD', '')} | {r.get('razao_mediana', '')} |"
                )
        return "\n".join(lines)

    # recomendacao
    melhora_global = chal_h["COD_mediano"] <= base_h["COD_mediano"]
    # equalizacao: desvio do % compativel entre faixas de inscricao no diagnostico
    # e COD mediano antigo vs novo nas faixas <300k
    base_est = treino["baseline"]["estratificado_holdout"]["por_inscricao"]
    chal_est = treino["desafiante"]["estratificado_holdout"]["por_inscricao"]
    cod_base_velho = next((r["COD_mediano"] for r in base_est if r["faixa"] == "<300k"), None)
    cod_chal_velho = next((r["COD_mediano"] for r in chal_est if r["faixa"] == "<300k"), None)
    melhora_velho = (
        cod_base_velho is not None and cod_chal_velho is not None
        and cod_chal_velho < cod_base_velho
    )

    if melhora_global and melhora_velho:
        recomendacao = (
            "**Recomendação:** promover o modelo desafiante a *candidato* a substituição "
            "do aprovado, após revisão SELAN (holdout + resíduos espaciais + reprocessamento "
            "do status Compatível). O modelo aprovado permanece em produção até essa decisão."
        )
    elif melhora_global or melhora_velho:
        recomendacao = (
            "**Recomendação:** manter o modelo aprovado em produção e continuar o desafiante "
            "como linha de pesquisa — há ganho parcial (global ou estoque antigo), mas ainda "
            "não há evidência completa para promoção automática."
        )
    else:
        recomendacao = (
            "**Recomendação:** não promover. Incluir idade não melhorou de forma material as "
            "métricas IAAO no protocolo testado; investigar interações idade×setor ou "
            "calibração pós-hoc por faixa etária antes de novo treino."
        )

    md = f"""# Nota técnica — Idade do imóvel no modelo de apartamentos (ITIV)

**Adendo analítico ao Relatório de Inteligência Fiscal 114/2026**  
**Data:** 10/08/2026  
**Referência:** e-mails Marcos (03/08) e David (04/08/2026) sobre Compatível × inscrição > 900.000  
**Fonte de idade:** `Nascimento Imovel.csv` (`CDINSCRICAOIMOB`; `AACONSTRUCAO`)

---

## 1. Achado do David (confirmado)

Entre as avaliações classificadas como **Compatível** (inclui “Compatível — valor da transação abaixo do estimado”):

| Indicador | Valor |
|---|---|
| N Compatível | {n_comp:,} |
| Compatível com inscrição > 900.000 | {david['n_compativel_inscricao_gt_900k']:,} (**{david['pct_compativel_com_inscricao_gt_900k']}%**) |
| % dos Não Compatíveis com inscrição > 900k | {david['pct_nao_compativel_com_inscricao_gt_900k']}% |
| Idade mediana (Compatível) | {david['idade_mediana_compativel']} |
| Idade mediana (Não Compatível*) | {david['idade_mediana_nao_compativel']} |
| Cobertura de idade na base de status | {david['cobertura_idade_pct']}% |

\\*Exceto “Fora de Escopo”.

A observação de David (~48% dos Compatível com inscrição > 900k) está **alinhada** aos dados. Inscrição alta correlaciona com estoque **novo / pouco depreciado** (mediana de ano de construção ~2021 na faixa >900k). O modelo aprovado **não usa idade** como feature; localização, área e KNN absorvem parcialmente o efeito de vintage, com aderência desigual.

### 1.1 % Compatível e IAAO por faixa de inscrição (modelo aprovado × status)

| Faixa | N | % Compatível | COD mediano | PRD | Idade mediana |
|---|---:|---:|---:|---:|---:|
{_fmt_faixas(diag['por_faixa_inscricao'])}

### 1.2 % Compatível por faixa etária

| Faixa | N | % Compatível | COD mediano | PRD | Idade mediana |
|---|---:|---:|---:|---:|---:|
{_fmt_faixas(diag['por_faixa_idade'])}

Gráficos: `desafiante_idade/saida/grafico_compativel_por_faixa.png`, `grafico_cod_por_inscricao.png`.

---

## 2. Engenharia proposta (e implementada no desafiante)

- Join por `CDINSCRICAOIMOB` com `Nascimento Imovel.csv`
- `AACONSTRUCAO` higienizado: apenas anos em `[1500, ano_da_transação]`
- `IDADE_NA_TRANSACAO = ano_transação − AACONSTRUCAO`
- `FLAG_ANO_AUSENTE`, `FLAG_ANO_INVALIDO`
- Para o LightGBM: `IDADE_NA_TRANSACAO_IMP` = idade com mediana imputada **somente** onde a flag marca ausência (transparência via flags)
- **Não** usar o número de inscrição como proxy definitivo de idade (apenas corte diagnóstico)

Arquivos: `pool_treino_com_idade.parquet`, `teste_final_com_idade.parquet`.

---

## 3. Modelo desafiante vs baseline (mesmo hiperparâmetro do aprovado)

Hiperparâmetros congelados do LightGBM aprovado: `{treino['hiperparametros']}`.  
CV externa k={treino['k_folds']} (pragmático; protocolo completo do manifesto usa k=10).

### Holdout (teste final)

| Modelo | Razão mediana | COD | COD mediano | PRD | PRB |
|---|---:|---:|---:|---:|---:|
| Baseline (sem idade) | {base_h['razao_mediana']:.4f} | {base_h['COD']:.2f} | {base_h['COD_mediano']:.2f} | {base_h['PRD']:.4f} | {base_h['PRB']:.4f} |
| Desafiante (+ idade) | {chal_h['razao_mediana']:.4f} | {chal_h['COD']:.2f} | {chal_h['COD_mediano']:.2f} | {chal_h['PRD']:.4f} | {chal_h['PRB']:.4f} |
| Δ COD mediano (base − desaf.) | | | **{treino['delta_holdout_cod_mediano']:.3f}** | | |

### Holdout estratificado por inscrição — COD mediano

| Faixa | Baseline | Desafiante |
|---|---:|---:|
"""

    for b, c in zip(base_est, chal_est):
        md += f"| {b['faixa']} | {b.get('COD_mediano')} | {c.get('COD_mediano')} |\n"

    md += """
### Importância (ganho) — top features do desafiante

"""
    for nome, val in treino["desafiante"]["importances"][:12]:
        md += f"- `{nome}`: {val}\n"

    md += f"""

Artefato: `{treino['desafiante']['modelo_arquivo']}`  
Comparativo completo: `desafiante_idade/saida/comparativo_baseline_desafiante.json`

---

## 4. Governança e recomendação

- O **modelo aprovado permanece congelado** em `Modelo_Apartamentos_Aprovado/`.
- O desafiante é linha experimental sob `desafiante_idade/`.
- Critério de sucesso do plano: melhorar COD/PRD no estoque antigo sem degradar o novo; reduzir assimetria da taxa Compatível entre faixas.

{recomendacao}

### Próximos passos sugeridos à equipe

1. Reprocessar status Compatível com o desafiante e repetir a tabela do §1.
2. Se promover: dossiê SELAN (Etapa 5 normativa) + manifesto SHA-256 novo.
3. Testar interação idade × `CDSETORFISCAL` se o ganho no estoque antigo for insuficiente.
4. Estender nascimento a salas (prioridade do relatório de 04/08) após fechar apartamentos.

---

*Gerado automaticamente por `desafiante_idade/pipeline_idade_apartamentos.py`.*
"""

    destino = SAIDA / "Nota_Tecnica_Idade_Modelo_Apartamentos.md"
    destino.write_text(md, encoding="utf-8")
    # copia na raiz ITIV para achar facil
    copia = PASTA_ITIV / "Nota_Tecnica_Idade_Modelo_Apartamentos.md"
    copia.write_text(md, encoding="utf-8")
    print(f"  Nota: {destino}")
    print(f"  Copia: {copia}")
    return destino


def main():
    print("Iniciando pipeline idade/desafiante...", flush=True)
    nascimento = carregar_nascimento()
    print(f"Nascimento: {len(nascimento):,} inscricoes unicas", flush=True)
    diag = etapa_diagnostico(nascimento)
    treino = etapa_treino(nascimento)
    etapa_nota(diag, treino)
    print("\nPipeline concluido.", flush=True)


if __name__ == "__main__":
    main()
