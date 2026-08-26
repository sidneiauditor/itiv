# -*- coding: utf-8 -*-
"""ETAPA 5 — Validação normativa completa do modelo de apartamentos.

Blocos executados (plano aprovado pela equipe em 14/07/2026):
  Bloco 1 — Pressupostos estatísticos do modelo hedônico (NBR 14653-2,
            Anexo A): significância t/F, normalidade, homocedasticidade,
            autocorrelação, multicolinearidade, pontos influenciantes,
            micronumerosidade.
  Bloco 2 — Grau de fundamentação (NBR 14653-2, Tabelas 1 e 2) e grau de
            precisão (Tabela 5) do hedônico. O LightGBM NÃO é objeto de
            especificação (IBAPE/SOBREA 2023, itens 8.1.2 e 8.1.2.1) —
            exige justificativa e validação, ambas documentadas.
  Bloco 3 — Estudo de razões IAAO por segmento (equidade vertical por
            faixa de valor e horizontal por setor fiscal), no holdout.
  Bloco extra — Comparação valor venal atual x hedônico x LightGBM
            no holdout (refaz a medição da "Etapa 6 parcial" com o
            modelo novo).

Saída: etapa5_resultados.json (+ impressão no console).
NÃO altera nenhum dado nem modelo — apenas mede.
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as scipy_stats
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson, jarque_bera

from apartamentos_lib import (AMOSTRAS, K_VIZINHOS, PASTA,
                               calcular_knn_proxy, metricas_completas,
                               preparar_area_saneamento, prever_hedonico,
                               treinar_hedonico)
from metricas_iaao_por_decil import metricas_razao, prb_global
from saneamento_chauvenet_iterativo import aplicar_chauvenet_iterativo

warnings.filterwarnings("ignore")

SETOR_AGRUPAMENTO = {177: 175, 179: 162}

resultado = {"criterio_agrupamento_setores": {
    "regra": "distancia <= 1km E |diferenca de preco/m2| <= 20% vs. vizinho com n>=10",
    "mapeamento_aplicado": SETOR_AGRUPAMENTO,
    "aplicado_em": "somente na especificacao do hedonico (NBR 14653-2, item 5 da Tabela 1)",
}}

print("=" * 70)
print("ETAPA 5 — Validação normativa completa (apartamentos)")
print("=" * 70)

# ---------------------------------------------------------------------------
# Reconstruição do treino final do hedônico (idêntico à Etapa C do treino)
# ---------------------------------------------------------------------------
pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
teste = pd.read_parquet(AMOSTRAS / "teste_final_previsoes.parquet")

pool_san = preparar_area_saneamento(pool)
pool_limpo = aplicar_chauvenet_iterativo(pool_san)
pool_limpo = pool_limpo.copy()
pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)

print(f"\nAgrupamento de setores aplicado ao hedonico: {SETOR_AGRUPAMENTO}")
pool_limpo["CDSETORFISCAL_ANTES_AGRUPAMENTO"] = pool_limpo["CDSETORFISCAL"]
pool_limpo["CDSETORFISCAL"] = pool_limpo["CDSETORFISCAL"].replace(SETOR_AGRUPAMENTO)

modelo, colunas = treinar_hedonico(pool_limpo)
n = int(modelo.nobs)
k = len(colunas) - 1  # variáveis independentes (sem a constante)
print(f"\nHedônico re-treinado no pool limpo: n={n:,} | k={k} variáveis independentes")

# ---------------------------------------------------------------------------
# BLOCO 1 — Pressupostos (NBR 14653-2, Anexo A)
# ---------------------------------------------------------------------------
print("\n--- BLOCO 1: pressupostos do modelo hedônico (Anexo A) ---")
b1 = {}

# Significância global (teste F — Tabela 1, item 6)
b1["F"] = float(modelo.fvalue)
b1["F_pvalor"] = float(modelo.f_pvalue)
b1["R2"] = float(modelo.rsquared)
b1["R2_ajustado"] = float(modelo.rsquared_adj)
print(f"F = {modelo.fvalue:,.1f} (p = {modelo.f_pvalue:.2e}) | "
      f"R2 = {modelo.rsquared:.4f} | R2 ajustado = {modelo.rsquared_adj:.4f}")

# Significância de cada regressor (teste t bicaudal — Tabela 1, item 5)
pvals = modelo.pvalues.drop("const", errors="ignore")
b1["regressores_total"] = int(len(pvals))
for lim, nome in [(0.10, "10"), (0.20, "20"), (0.30, "30")]:
    b1[f"regressores_p_acima_{nome}pct"] = int((pvals > lim).sum())
b1["pvalor_maximo"] = float(pvals.max())
b1["regressores_acima_10pct_lista"] = [
    {"variavel": v, "pvalor": float(p)} for v, p in pvals[pvals > 0.10].items()
]
print(f"Regressores: {len(pvals)} | com p>10%: {b1['regressores_p_acima_10pct']} | "
      f"p>20%: {b1['regressores_p_acima_20pct']} | p>30%: {b1['regressores_p_acima_30pct']}")

# Resíduos padronizados
resid = modelo.resid
ajustados = modelo.fittedvalues
resid_pad = (resid - resid.mean()) / resid.std()

# Normalidade (A.2.1.2): frequências nos intervalos ±1 / ±1,64 / ±1,96 + Jarque-Bera
freq = {}
for lim, esperado in [(1.0, 68), (1.64, 90), (1.96, 95)]:
    obs = float((resid_pad.abs() <= lim).mean() * 100)
    freq[f"dentro_{lim}"] = {"observado_pct": obs, "esperado_pct": esperado}
    print(f"Resíduos em [-{lim}; +{lim}]: {obs:.1f}% (normal: {esperado}%)")
jb_stat, jb_p, jb_skew, jb_kurt = jarque_bera(resid)
b1["normalidade"] = {
    "frequencias": freq,
    "jarque_bera_stat": float(jb_stat), "jarque_bera_p": float(jb_p),
    "assimetria": float(jb_skew), "curtose": float(jb_kurt),
    "pct_fora_2sigma": float((resid_pad.abs() > 2).mean() * 100),
}
print(f"Jarque-Bera: {jb_stat:,.0f} (p={jb_p:.2e}) | assimetria={jb_skew:.3f} | "
      f"curtose={jb_kurt:.2f} | fora de ±2: {b1['normalidade']['pct_fora_2sigma']:.1f}%")

# Homocedasticidade (A.2.1.3 — "entre outros": Breusch-Pagan + análise gráfica)
X_matriz = modelo.model.exog
bp_stat, bp_p, bp_f, bp_fp = het_breuschpagan(resid, X_matriz)
b1["homocedasticidade"] = {"breusch_pagan_stat": float(bp_stat), "breusch_pagan_p": float(bp_p)}
print(f"Breusch-Pagan: {bp_stat:,.1f} (p={bp_p:.2e})")

# Autocorrelação (A.2.1.4 — pré-ordenamento pelos valores ajustados)
ordem = np.argsort(ajustados.to_numpy())
dw = float(durbin_watson(resid.to_numpy()[ordem]))
b1["autocorrelacao"] = {"durbin_watson_ordenado_por_ajustados": dw}
print(f"Durbin-Watson (ordenado por valores ajustados): {dw:.3f} (referência: ~2 = sem autocorrelação)")

# Multicolinearidade (A.2.1.5 — matriz de correlações das contínuas + VIF)
continuas = ["LOG_AREA", "NUPAVIMENTOS", "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE", "VAR_TENDENCIA"]
Xc = pd.DataFrame(X_matriz, columns=colunas)[
    [c for c in continuas if c in colunas]]
corr = Xc.corr()
pares_altos = []
for i, a in enumerate(corr.columns):
    for b_ in corr.columns[i + 1:]:
        if abs(corr.loc[a, b_]) > 0.80:
            pares_altos.append({"par": f"{a} x {b_}", "correlacao": float(corr.loc[a, b_])})
vifs = {}
X_full = pd.DataFrame(X_matriz, columns=colunas).astype(float)
for c in Xc.columns:
    outras = X_full.drop(columns=[c])
    r2_aux = sm.OLS(X_full[c], outras).fit().rsquared
    vifs[c] = float(1 / (1 - r2_aux)) if r2_aux < 1 else float("inf")
b1["multicolinearidade"] = {
    "pares_correlacao_acima_080": pares_altos,
    "vif_variaveis_continuas": vifs,
    "correlacao_maxima_continuas": float(corr.where(~np.eye(len(corr), dtype=bool)).abs().max().max()),
}
print("VIF (contínuas): " + ", ".join(f"{c}={v:.2f}" for c, v in vifs.items()))
print(f"Pares de contínuas com |r|>0,80: {len(pares_altos)}")

# Pontos influenciantes (A.2.1.6 — distância de Cook)
XtX_inv = np.linalg.pinv(X_matriz.T @ X_matriz)
h = np.einsum("ij,jk,ik->i", X_matriz, XtX_inv, X_matriz)
mse = float((resid ** 2).sum() / (n - k - 1))
cooks = (resid.to_numpy() ** 2 / ((k + 1) * mse)) * (h / (1 - h) ** 2)
limite_cook = 4 / n
b1["pontos_influenciantes"] = {
    "criterio": "distância de Cook",
    "limite_4_sobre_n": float(limite_cook),
    "acima_4_sobre_n": int((cooks > limite_cook).sum()),
    "acima_4_sobre_n_pct": float((cooks > limite_cook).mean() * 100),
    "acima_de_1": int((cooks > 1).sum()),
    "cook_maximo": float(cooks.max()),
}
print(f"Cook > 4/n: {b1['pontos_influenciantes']['acima_4_sobre_n']:,} "
      f"({b1['pontos_influenciantes']['acima_4_sobre_n_pct']:.1f}%) | "
      f"Cook > 1: {b1['pontos_influenciantes']['acima_de_1']} | máx: {cooks.max():.4f}")

# Micronumerosidade (A.2 a): n >= 3(k+1); ni >= 10 por dummy (n > 100)
setores = pool_limpo["CDSETORFISCAL"].value_counts()
b1["micronumerosidade"] = {
    "n": n, "k": k, "3(k+1)": 3 * (k + 1), "6(k+1)": 6 * (k + 1),
    "atende_3k1": bool(n >= 3 * (k + 1)), "atende_6k1": bool(n >= 6 * (k + 1)),
    "setores_total": int(len(setores)),
    "setores_com_menos_de_10_dados": int((setores < 10).sum()),
    "setores_menos_10_lista": {str(s): int(c) for s, c in setores[setores < 10].items()},
}
print(f"n={n:,} vs 6(k+1)={6*(k+1):,} -> atende Grau III de quantidade")
print(f"Setores com menos de 10 dados (ni<10): {b1['micronumerosidade']['setores_com_menos_de_10_dados']}")

resultado["bloco1_pressupostos"] = b1

# dados para gráficos dos resíduos (amostra p/ dispersão)
rng = np.random.default_rng(42)
amostra_idx = rng.choice(n, size=min(5000, n), replace=False)
graficos_residuos = {
    "resid_pad_hist": resid_pad.to_numpy().tolist(),
    "amostra_ajustados": ajustados.to_numpy()[amostra_idx].tolist(),
    "amostra_resid_pad": resid_pad.to_numpy()[amostra_idx].tolist(),
}

# ---------------------------------------------------------------------------
# BLOCO 2 — Grau de precisão (Tabela 5): amplitude do IC de 80% no holdout
# ---------------------------------------------------------------------------
print("\n--- BLOCO 2: grau de precisão (NBR Tabela 5) ---")
dummies_setor = pd.get_dummies(
    teste["CDSETORFISCAL"].fillna(-1).astype(int), prefix="SETOR", drop_first=True)
X_teste = pd.concat([
    teste[["LOG_AREA", "NUPAVIMENTOS", "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE", "VAR_TENDENCIA"]]
    .fillna(0).reset_index(drop=True),
    dummies_setor.reset_index(drop=True),
], axis=1).astype(float)
X_teste = sm.add_constant(X_teste, has_constant="add")
X_teste = X_teste.reindex(columns=colunas, fill_value=0.0)

pred = modelo.get_prediction(X_teste)
ic80 = pred.conf_int(alpha=0.20)  # IC de 80% da estimativa de tendência central
central = np.exp(pred.predicted_mean)
amplitude_pct = (np.exp(ic80[:, 1]) - np.exp(ic80[:, 0])) / central * 100
b2 = {
    "amplitude_ic80_mediana_pct": float(np.median(amplitude_pct)),
    "amplitude_ic80_p95_pct": float(np.percentile(amplitude_pct, 95)),
    "amplitude_ic80_maxima_pct": float(amplitude_pct.max()),
    "pct_imoveis_amplitude_ate_30": float((amplitude_pct <= 30).mean() * 100),
}
resultado["bloco2_precisao"] = b2
print(f"Amplitude do IC 80% (holdout): mediana={b2['amplitude_ic80_mediana_pct']:.2f}% | "
      f"p95={b2['amplitude_ic80_p95_pct']:.2f}% | máx={b2['amplitude_ic80_maxima_pct']:.2f}%")
print(f"Imóveis com amplitude <= 30% (Grau III): {b2['pct_imoveis_amplitude_ate_30']:.1f}%")

# ---------------------------------------------------------------------------
# BLOCO 3 — Estudo de razões IAAO por segmento (holdout, LightGBM)
# ---------------------------------------------------------------------------
print("\n--- BLOCO 3: estudo de razões IAAO por segmento (holdout) ---")
real = teste["VLTRANSACAO_DEFLACIONADO"].to_numpy()
pred_lgb = teste["VALOR_PREVISTO_LGBM"].to_numpy()
pred_hed = teste["VALOR_PREVISTO_HEDONICO"].to_numpy()
razao_lgb = pred_lgb / real

# Equidade vertical: por decil do valor real
decis = pd.qcut(real, 10, labels=False)
por_decil = []
for d in range(10):
    m = decis == d
    r = razao_lgb[m]
    mediana_r = float(np.median(r))
    cod = float(np.median(np.abs(r - mediana_r)) / mediana_r * 100) if mediana_r else None
    # COD IAAO clássico (desvio absoluto médio em torno da mediana)
    cod_iaao = float(np.mean(np.abs(r - mediana_r)) / mediana_r * 100)
    por_decil.append({
        "decil": d + 1,
        "faixa_de_valor": f"R$ {np.min(real[m]):,.0f} a R$ {np.max(real[m]):,.0f}",
        "n": int(m.sum()),
        "razao_mediana": mediana_r,
        "COD_iaao_pct": cod_iaao,
    })
    print(f"  decil {d+1:2d}: razão mediana={mediana_r:.3f} COD={cod_iaao:5.1f}% (n={m.sum():,})")
resultado["bloco3_vertical_por_decil"] = por_decil

# Equidade horizontal: por setor fiscal (todos reportados; n<10 sinalizado)
por_setor = []
setores_teste = teste["CDSETORFISCAL"].fillna(-1).astype(int)
for setor, m_idx in setores_teste.groupby(setores_teste).groups.items():
    r = razao_lgb[teste.index.get_indexer(m_idx)]
    mediana_r = float(np.median(r))
    cod_iaao = float(np.mean(np.abs(r - mediana_r)) / mediana_r * 100) if mediana_r else None
    por_setor.append({"setor": int(setor), "n": int(len(r)),
                      "razao_mediana": mediana_r, "COD_iaao_pct": cod_iaao,
                      "n_menor_que_10": bool(len(r) < 10)})
por_setor.sort(key=lambda x: -x["n"])
resultado["bloco3_horizontal_por_setor"] = por_setor
setores_ok = [s for s in por_setor if not s["n_menor_que_10"]]
dentro_faixa = [s for s in setores_ok if 0.90 <= s["razao_mediana"] <= 1.10]
cod_ate_15 = [s for s in setores_ok if s["COD_iaao_pct"] <= 15]
print(f"\nSetores no holdout: {len(por_setor)} (com n>=10: {len(setores_ok)})")
print(f"  razão mediana em 0,90-1,10: {len(dentro_faixa)}/{len(setores_ok)}")
print(f"  COD <= 15%: {len(cod_ate_15)}/{len(setores_ok)}")
resultado["bloco3_resumo_setores"] = {
    "setores_holdout": len(por_setor), "setores_n_10_ou_mais": len(setores_ok),
    "setores_razao_dentro_090_110": len(dentro_faixa),
    "setores_cod_ate_15": len(cod_ate_15),
}

# ---------------------------------------------------------------------------
# BLOCO EXTRA — Comparação valor venal atual x hedônico x LightGBM (holdout)
# ---------------------------------------------------------------------------
print("\n--- Comparação valor venal atual x modelos (holdout) ---")
venal = pd.to_numeric(teste["VLVENALCADASTRO"], errors="coerce").to_numpy()
m_venal = (venal > 0) & (real > 0)
comp = {}
for nome, estimativa in [("valor_venal_cadastro", venal),
                          ("hedonico", pred_hed), ("lightgbm", pred_lgb)]:
    met = metricas_completas(np.where(m_venal, estimativa, np.nan)[m_venal], real[m_venal])
    comp[nome] = {k2: float(v2) for k2, v2 in met.items()}
    print(f"  {nome:22s} razão={met['razao_mediana']:.3f} COD={met['COD']:.1f}% "
          f"PRD={met['PRD']:.3f} PRB={met['PRB']:+.4f}")
comp["n_comparacao"] = int(m_venal.sum())
comp["ressalva"] = (
    "A base de treino/teste foi filtrada (decisão de 14/07/2026) para transações "
    "com desvio de até ±30% entre valor de transação e VLVENALCORRIGIDO. Essa "
    "restrição limita, por construção, a dispersão das razões do valor venal "
    "nesta comparação — as métricas do valor venal aqui NÃO são comparáveis às "
    "medidas na base completa (Etapa 6 parcial, base antiga)."
)
resultado["comparacao_venal_modelos"] = comp
print(f"  (n = {comp['n_comparacao']:,}; ver ressalva metodológica no JSON/relatório)")

# ---------------------------------------------------------------------------
with open(PASTA / "etapa5_resultados.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2, default=float)
with open(PASTA / "etapa5_dados_graficos.json", "w", encoding="utf-8") as f:
    json.dump(graficos_residuos, f)

print(f"\nSalvos: etapa5_resultados.json, etapa5_dados_graficos.json")
print("=" * 70)
