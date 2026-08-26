# -*- coding: utf-8 -*-
"""ETAPA 4.4 — Treino do modelo de apartamentos: hedonico (OLS) + LightGBM,
validados por k-fold cross-validation (k=10, D7), com Chauvenet iterativo e
proxy KNN de vizinhanca recalculados DENTRO de cada fold (nunca vazando dados
de fora do treino do fold).

Sequencia:
  A. GridSearch MULTI-MODELO (CV interno k=5) sobre o POOL inteiro (D6 —
     "execute o GridSearch para achar um modelo que melhor se encaixe no
     problema"; ampliado em 14/07/2026 a pedido da equipe para testar outras
     familias alem do LightGBM): LightGBM (grade ampliada), Floresta
     Aleatoria, Extra Trees, HistGradientBoosting e ElasticNet. Vence o de
     menor erro absoluto medio (MAE) no log do valor, na CV interna.
  B. Validacao cruzada externa k=10 (D7): em cada fold, Chauvenet iterativo e
     KNN proxy sao recalculados so com o treino do fold; treina hedonico e o
     modelo VENCEDOR da etapa A e mede no fold de validacao.
  C. Treino final no POOL inteiro (modelo vencedor) e avaliacao UNICA no
     TESTE FINAL (holdout, nunca tocado antes).

Nota de escopo (pragmatica, nao normativa): o GridSearch (etapa A) roda uma
vez sobre o pool inteiro (com CV interno proprio) por custo computacional —
refazer o grid completo dentro de cada um dos 10 folds externos multiplicaria
o tempo de treino por dezenas de vezes sem ganho pratico de decisao (os
hiperparametros vencedores tendem a ser estaveis). Os folds externos (etapa B)
SAO isolados de vazamento: Chauvenet e KNN recalculados por fold.
"""
import json
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (ExtraTreesRegressor,
                              HistGradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import GridSearchCV, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from apartamentos_lib import (AMOSTRAS, CAT_LGBM, FEATURES_LGBM, K_FOLDS,
                               K_VIZINHOS, PASTA, SEMENTE, calcular_knn_proxy,
                               metricas_completas, montar_X_numerico,
                               montar_X_y, preparar_area_saneamento,
                               prever_hedonico, treinar_hedonico)
from saneamento_chauvenet_iterativo import aplicar_chauvenet_iterativo

warnings.filterwarnings("ignore")

print("=" * 70)
print("ETAPA 4.4 — Treino do modelo de apartamentos")
print("=" * 70)

pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
teste_final = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")
print(f"\nPool (treino/CV): {len(pool):,} | Teste final (holdout): {len(teste_final):,}")

# ---------------------------------------------------------------------------
# ETAPA A — GridSearch MULTI-MODELO sobre o pool inteiro (CV interno k=5)
# Ampliado em 14/07/2026 a pedido da equipe: alem do LightGBM (grade maior),
# concorrem Floresta Aleatoria, Extra Trees, HistGradientBoosting e ElasticNet
# (todas as bibliotecas ja instaladas; sem novos pacotes).
# ---------------------------------------------------------------------------
print("\n--- Etapa A: GridSearch multi-modelo (CV interno k=5, sobre o pool) ---")
pool_san = preparar_area_saneamento(pool)
pool_limpo_gs = aplicar_chauvenet_iterativo(pool_san)
pool_limpo_gs = pool_limpo_gs.copy()
pool_limpo_gs["KNN_PROXY"] = calcular_knn_proxy(pool_limpo_gs, pool_limpo_gs, k=K_VIZINHOS)

X_gs, y_gs, mediana_proxy_global = montar_X_y(pool_limpo_gs)
X_gs_num, _, _ = montar_X_numerico(pool_limpo_gs, mediana_proxy=mediana_proxy_global)

NUM_COLS = [c for c in FEATURES_LGBM if c != "CDSETORFISCAL"]

# Pre-processamento para o modelo linear: imputa mediana + padroniza os
# numericos; setor fiscal vira dummies (one-hot), como no hedonico.
pre_linear = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                      ("sc", StandardScaler())]), NUM_COLS),
    ("cat", OneHotEncoder(handle_unknown="ignore"), ["CDSETORFISCAL"]),
])

CANDIDATOS = {
    "lightgbm": {
        "estimador": lgb.LGBMRegressor(random_state=SEMENTE, verbosity=-1),
        "grade": {
            "num_leaves": [15, 31, 63],
            "learning_rate": [0.05, 0.1],
            "n_estimators": [200, 400, 800],
            "min_child_samples": [20, 50],
        },
        "X": X_gs,
        "fit_params": {"categorical_feature": CAT_LGBM},
    },
    "hist_gradient_boosting": {
        "estimador": HistGradientBoostingRegressor(random_state=SEMENTE),
        "grade": {
            "learning_rate": [0.05, 0.1],
            "max_iter": [300, 600],
            "max_leaf_nodes": [31, 63],
        },
        "X": X_gs_num,
        "fit_params": {},
    },
    "random_forest": {
        "estimador": Pipeline([("imp", SimpleImputer(strategy="median")),
                                ("modelo", RandomForestRegressor(random_state=SEMENTE))]),
        "grade": {
            "modelo__n_estimators": [300],
            "modelo__max_depth": [None, 20],
            "modelo__min_samples_leaf": [1, 5],
        },
        "X": X_gs_num,
        "fit_params": {},
    },
    "extra_trees": {
        "estimador": Pipeline([("imp", SimpleImputer(strategy="median")),
                                ("modelo", ExtraTreesRegressor(random_state=SEMENTE))]),
        "grade": {
            "modelo__n_estimators": [300],
            "modelo__max_depth": [None, 20],
            "modelo__min_samples_leaf": [1, 5],
        },
        "X": X_gs_num,
        "fit_params": {},
    },
    "elasticnet": {
        "estimador": Pipeline([("pre", pre_linear),
                                ("modelo", ElasticNet(random_state=SEMENTE, max_iter=5000))]),
        "grade": {
            "modelo__alpha": [0.0001, 0.001, 0.01, 0.1],
            "modelo__l1_ratio": [0.2, 0.5, 0.8],
        },
        "X": X_gs_num,
        "fit_params": {},
    },
}

resultados_gs = {}
for nome, cfg in CANDIDATOS.items():
    gs = GridSearchCV(cfg["estimador"], cfg["grade"], cv=5,
                      scoring="neg_mean_absolute_error", n_jobs=-1)
    gs.fit(cfg["X"], y_gs, **cfg["fit_params"])
    resultados_gs[nome] = {
        "melhor_estimador": gs.best_estimator_,
        "params": gs.best_params_,
        "mae_log_cv": float(-gs.best_score_),
    }
    print(f"  {nome:24s} MAE(log)={-gs.best_score_:.4f}  params={gs.best_params_}")

NOME_VENCEDOR = min(resultados_gs, key=lambda n: resultados_gs[n]["mae_log_cv"])
melhores_params = resultados_gs["lightgbm"]["params"]  # sempre registrado (usado pelo D5)
print(f"\nVENCEDOR do GridSearch multi-modelo: {NOME_VENCEDOR} "
      f"(MAE log = {resultados_gs[NOME_VENCEDOR]['mae_log_cv']:.4f})")


def montar_X_ml(df, mediana_proxy=None):
    """Monta X/y no formato que o modelo vencedor espera."""
    if NOME_VENCEDOR == "lightgbm":
        return montar_X_y(df, mediana_proxy)
    return montar_X_numerico(df, mediana_proxy)


def ajustar_ml(X, y):
    """Clona o vencedor (com os melhores hiperparametros) e treina."""
    m = clone(resultados_gs[NOME_VENCEDOR]["melhor_estimador"])
    if NOME_VENCEDOR == "lightgbm":
        m.fit(X, y, categorical_feature=CAT_LGBM)
    else:
        m.fit(X, y)
    return m

# ---------------------------------------------------------------------------
# ETAPA B — Validacao cruzada externa k=10 (isolamento por fold)
# ---------------------------------------------------------------------------
print(f"\n--- Etapa B: validacao cruzada externa (k={K_FOLDS}) ---")
kf = KFold(n_splits=K_FOLDS, shuffle=True, random_state=SEMENTE)
pool = pool.reset_index(drop=True)

metricas_hed_folds, metricas_lgb_folds = [], []

for i, (idx_tr, idx_val) in enumerate(kf.split(pool), start=1):
    treino_fold = pool.iloc[idx_tr].copy()
    val_fold = pool.iloc[idx_val].copy()

    # Chauvenet iterativo SO no treino do fold
    treino_fold = preparar_area_saneamento(treino_fold)
    treino_fold_limpo = aplicar_chauvenet_iterativo(treino_fold)

    # KNN proxy: base = treino do fold; alvo = treino limpo (self, causal) e val do fold
    treino_fold_limpo = treino_fold_limpo.copy()
    treino_fold_limpo["KNN_PROXY"] = calcular_knn_proxy(treino_fold_limpo, treino_fold_limpo, k=K_VIZINHOS)
    val_fold = val_fold.copy()
    val_fold["KNN_PROXY"] = calcular_knn_proxy(treino_fold_limpo, val_fold, k=K_VIZINHOS)

    # Hedonico
    modelo_hed, colunas_hed = treinar_hedonico(treino_fold_limpo)
    pred_hed_log = prever_hedonico(modelo_hed, colunas_hed, val_fold)
    pred_hed = np.exp(pred_hed_log)

    # Modelo ML vencedor do GridSearch multi-modelo
    X_tr, y_tr, mediana_fold = montar_X_ml(treino_fold_limpo)
    X_val, y_val, _ = montar_X_ml(val_fold, mediana_proxy=mediana_fold)
    modelo_ml = ajustar_ml(X_tr, y_tr)
    pred_ml = np.exp(modelo_ml.predict(X_val))

    real = val_fold["VLTRANSACAO_DEFLACIONADO"].to_numpy()
    met_hed = metricas_completas(pred_hed, real)
    met_lgb = metricas_completas(pred_ml, real)
    metricas_hed_folds.append(met_hed)
    metricas_lgb_folds.append(met_lgb)
    print(f"  fold {i:2d}/{K_FOLDS} — hedonico: CODmed={met_hed['COD_mediano']:.1f}% PRD={met_hed['PRD']:.3f} | "
          f"{NOME_VENCEDOR}: CODmed={met_lgb['COD_mediano']:.1f}% PRD={met_lgb['PRD']:.3f}")

def resumo(metricas_folds, nome):
    df_m = pd.DataFrame(metricas_folds)
    print(f"\n{nome} — media (+/- desvio) nos {K_FOLDS} folds:")
    for col in ["razao_mediana", "COD", "COD_mediano", "PRD", "PRB"]:
        print(f"  {col:15s}: {df_m[col].mean():.4f} +/- {df_m[col].std():.4f}")
    return df_m

resumo_hed = resumo(metricas_hed_folds, "HEDONICO")
resumo_lgb = resumo(metricas_lgb_folds, NOME_VENCEDOR.upper())

# ---------------------------------------------------------------------------
# ETAPA C — Treino final no pool inteiro + avaliacao UNICA no teste final
# ---------------------------------------------------------------------------
print("\n--- Etapa C: treino final (pool inteiro) + avaliacao no teste final (holdout) ---")
pool_final = preparar_area_saneamento(pool)
pool_final_limpo = aplicar_chauvenet_iterativo(pool_final)
pool_final_limpo = pool_final_limpo.copy()
pool_final_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_final_limpo, pool_final_limpo, k=K_VIZINHOS)

teste_final = teste_final.copy()
teste_final["KNN_PROXY"] = calcular_knn_proxy(pool_final_limpo, teste_final, k=K_VIZINHOS)

modelo_hed_final, colunas_hed_final = treinar_hedonico(pool_final_limpo)
pred_hed_teste = np.exp(prever_hedonico(modelo_hed_final, colunas_hed_final, teste_final))

X_pool, y_pool, mediana_pool = montar_X_ml(pool_final_limpo)
X_teste, _, _ = montar_X_ml(teste_final, mediana_proxy=mediana_pool)
modelo_ml_final = ajustar_ml(X_pool, y_pool)
pred_lgb_teste = np.exp(modelo_ml_final.predict(X_teste))

real_teste = teste_final["VLTRANSACAO_DEFLACIONADO"].to_numpy()
met_hed_teste = metricas_completas(pred_hed_teste, real_teste)
met_lgb_teste = metricas_completas(pred_lgb_teste, real_teste)

print("\nHOLDOUT (teste final, nunca usado em treino/ajuste):")
print(f"  hedonico : razao={met_hed_teste['razao_mediana']:.3f} COD={met_hed_teste['COD']:.1f}% "
      f"CODmed={met_hed_teste['COD_mediano']:.1f}% PRD={met_hed_teste['PRD']:.3f} "
      f"PRB={met_hed_teste['PRB']:+.4f}")
print(f"  {NOME_VENCEDOR}: razao={met_lgb_teste['razao_mediana']:.3f} COD={met_lgb_teste['COD']:.1f}% "
      f"CODmed={met_lgb_teste['COD_mediano']:.1f}% PRD={met_lgb_teste['PRD']:.3f} "
      f"PRB={met_lgb_teste['PRB']:+.4f}")
print("\nNota: base preparada com o filtro da equipe de 14/07/2026 (Compra e Venda "
      "exato, VLITIV > 0, desvio venal x transacao <= 30%), que substituiu o corte "
      "de vendas simbolicas para viabilizar a leitura de PRD/PRB.")
print("\nMetas IAAO (D4): razao 0,90-1,10 | COD <=15% | PRD 0,98-1,03 | PRB +/-0,05")

# Salvar modelos e previsoes
teste_final["VALOR_PREVISTO_HEDONICO"] = pred_hed_teste
teste_final["VALOR_PREVISTO_LGBM"] = pred_lgb_teste  # nome mantido por compatibilidade
teste_final.to_parquet(AMOSTRAS / "teste_final_previsoes.parquet", index=False)

import shutil
import tempfile
if NOME_VENCEDOR == "lightgbm":
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = str(Path(tmpdir) / "modelo_lightgbm_apartamentos.txt")
        modelo_ml_final.booster_.save_model(tmp_path)
        shutil.move(tmp_path, str(PASTA / "modelo_lightgbm_apartamentos.txt"))
    arq_modelo = "modelo_lightgbm_apartamentos.txt"
else:
    import joblib
    arq_modelo = f"modelo_{NOME_VENCEDOR}_apartamentos.joblib"
    joblib.dump(modelo_ml_final, PASTA / arq_modelo)
    print(f"\n[ATENCAO] O vencedor NAO foi o LightGBM — salvo em {arq_modelo}. "
          "A integracao com o avaliador em producao precisa ser atualizada.")
with open(PASTA / "modelo_hedonico_resumo.txt", "w", encoding="utf-8") as f:
    f.write(modelo_hed_final.summary().as_text())

with open(PASTA / "metricas_cv_apartamentos.json", "w", encoding="utf-8") as f:
    json.dump({
        "modelo_vencedor": NOME_VENCEDOR,
        "gridsearch_multimodelo": {
            nome: {"melhores_params": r["params"], "mae_log_cv": r["mae_log_cv"]}
            for nome, r in resultados_gs.items()
        },
        "hiperparametros_lightgbm": melhores_params,
        "cv_hedonico_por_fold": metricas_hed_folds,
        "cv_lightgbm_por_fold": metricas_lgb_folds,
        "holdout_hedonico": met_hed_teste,
        "holdout_lightgbm": met_lgb_teste,
    }, f, ensure_ascii=False, indent=2, default=float)

print(f"\nSalvos: {arq_modelo}, modelo_hedonico_resumo.txt, "
      f"metricas_cv_apartamentos.json, amostras/teste_final_previsoes.parquet")
print("=" * 70)
