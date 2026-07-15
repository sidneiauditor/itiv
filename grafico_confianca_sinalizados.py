# -*- coding: utf-8 -*-
"""D5 — Tabela: nivel de confianca do intervalo de predicao (LightGBM)
x numero de contribuintes que seriam sinalizados (fora do intervalo), no
TESTE FINAL.

DECISAO DA EQUIPE (14/07/2026): nivel de confianca de 90% para a sinalizacao
(coeficiente de seguranca, D5), com o COD do modelo novo em maos. Os demais
niveis sao mantidos na tabela apenas como referencia comparativa.

Intervalo de predicao aproximado via quantile regression (LightGBM
objective='quantile') treinado nos mesmos folds/hiperparametros do modelo
principal, para os quantis correspondentes a cada nivel de confianca.
"""
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from apartamentos_lib import (CAT_LGBM, FEATURES_LGBM, SEMENTE,
                               calcular_knn_proxy, montar_X_y,
                               preparar_area_saneamento)
from saneamento_chauvenet_iterativo import aplicar_chauvenet_iterativo

PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
AMOSTRAS = PASTA / "amostras"

with open(PASTA / "metricas_cv_apartamentos.json", encoding="utf-8") as f:
    melhores_params = json.load(f)["hiperparametros_lightgbm"]

NIVEL_DECIDIDO = 0.90  # decisao da equipe (14/07/2026)
NIVEIS_CONFIANCA = [0.95, 0.90, 0.85, 0.80, 0.75]

print("=" * 70)
print("D5 — Confianca do intervalo de predicao x contribuintes sinalizados")
print("=" * 70)

pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")

pool_san = preparar_area_saneamento(pool)
pool_limpo = aplicar_chauvenet_iterativo(pool_san)
pool_limpo = pool_limpo.copy()
pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=10)
teste = teste.copy()
teste["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste, k=10)

X_pool, y_pool, mediana_proxy = montar_X_y(pool_limpo)
X_teste, _, _ = montar_X_y(teste, mediana_proxy=mediana_proxy)
valor_real = teste["VLTRANSACAO_DEFLACIONADO"].to_numpy()

print(f"\n{'confianca':>10s} {'quantil inf':>12s} {'quantil sup':>12s} {'sinalizados':>12s} {'%':>7s}")
resultados = []
for conf in NIVEIS_CONFIANCA:
    alpha = (1 - conf) / 2
    q_inf, q_sup = alpha, 1 - alpha

    modelos_q = {}
    for q, nome in [(q_inf, "inf"), (q_sup, "sup")]:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q, random_state=SEMENTE,
                               verbosity=-1, **melhores_params)
        m.fit(X_pool, y_pool, categorical_feature=CAT_LGBM)
        modelos_q[nome] = m

    pred_inf = np.exp(modelos_q["inf"].predict(X_teste))
    pred_sup = np.exp(modelos_q["sup"].predict(X_teste))
    fora = (valor_real < pred_inf) | (valor_real > pred_sup)
    n_fora = int(fora.sum())
    resultados.append({
        "confianca": conf, "quantil_inf": q_inf, "quantil_sup": q_sup,
        "sinalizados": n_fora, "pct_sinalizados": n_fora / len(valor_real) * 100,
        "nivel_decidido_pela_equipe": conf == NIVEL_DECIDIDO,
    })
    marca = "  <== DECIDIDO (14/07/2026)" if conf == NIVEL_DECIDIDO else ""
    print(f"{conf * 100:>9.0f}% {q_inf:>12.3f} {q_sup:>12.3f} {n_fora:>12,} "
          f"{n_fora / len(valor_real) * 100:>6.1f}%{marca}")

with open(PASTA / "confianca_vs_sinalizados.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2, default=float)

print(f"\nSalvo: confianca_vs_sinalizados.json ({len(valor_real):,} contribuintes no teste final)")
print(f"\nDecisao da equipe (14/07/2026, D5): nivel de confianca de "
      f"{NIVEL_DECIDIDO * 100:.0f}% para a sinalizacao.")
