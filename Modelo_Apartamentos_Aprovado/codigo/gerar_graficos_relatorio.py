# -*- coding: utf-8 -*-
"""Gera os graficos (PNG) para o relatorio da Etapa 4, a partir de
metricas_cv_apartamentos.json e confianca_vs_sinalizados.json.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
SAIDA = PASTA / "graficos_relatorio"
SAIDA.mkdir(exist_ok=True)

with open(PASTA / "metricas_cv_apartamentos.json", encoding="utf-8") as f:
    cv = json.load(f)
with open(PASTA / "confianca_vs_sinalizados.json", encoding="utf-8") as f:
    conf = json.load(f)

COR_HED = "#1A3A5C"
COR_LGB = "#C0392B"
plt.rcParams.update({
    "font.size": 18, "font.family": "sans-serif",
    "axes.titlesize": 20, "axes.labelsize": 18,
    "xtick.labelsize": 16, "ytick.labelsize": 16,
    "legend.fontsize": 16,
})
DPI = 200

# --- Grafico 1: COD_mediano por fold (hedonico x lightgbm) ---
folds = list(range(1, len(cv["cv_hedonico_por_fold"]) + 1))
cod_hed = [m["COD_mediano"] for m in cv["cv_hedonico_por_fold"]]
cod_lgb = [m["COD_mediano"] for m in cv["cv_lightgbm_por_fold"]]

fig, ax = plt.subplots(figsize=(13, 7.3))
ax.plot(folds, cod_hed, marker="o", markersize=9, linewidth=2.5, color=COR_HED, label="Hedônico (OLS)")
ax.plot(folds, cod_lgb, marker="o", markersize=9, linewidth=2.5, color=COR_LGB, label="LightGBM")
ax.axhline(15, color="gray", linestyle="--", linewidth=1, label="Meta IAAO (COD ≤ 15%)")
ax.set_xlabel("Fold (validação cruzada, k=10)")
ax.set_ylabel("COD mediano (%)")
ax.set_title("COD por fold — validação cruzada")
ax.set_xticks(folds)
ax.legend(frameon=False, fontsize=15)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "cod_por_fold.png", dpi=200)
plt.close(fig)

# --- Grafico 2: razao mediana por fold ---
razao_hed = [m["razao_mediana"] for m in cv["cv_hedonico_por_fold"]]
razao_lgb = [m["razao_mediana"] for m in cv["cv_lightgbm_por_fold"]]

fig, ax = plt.subplots(figsize=(13, 7.3))
ax.plot(folds, razao_hed, marker="o", markersize=9, linewidth=2.5, color=COR_HED, label="Hedônico (OLS)")
ax.plot(folds, razao_lgb, marker="o", markersize=9, linewidth=2.5, color=COR_LGB, label="LightGBM")
ax.axhspan(0.90, 1.10, color="gray", alpha=0.15, label="Meta IAAO (0,90–1,10)")
ax.set_xlabel("Fold (validação cruzada, k=10)")
ax.set_ylabel("Razão mediana (avaliação / preço)")
ax.set_title("Nível geral por fold — validação cruzada")
ax.set_xticks(folds)
ax.legend(frameon=False, fontsize=15)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "razao_por_fold.png", dpi=200)
plt.close(fig)

# --- Grafico 3: comparativo holdout (barras) ---
holdout_hed = cv["holdout_hedonico"]
holdout_lgb = cv["holdout_lightgbm"]

fig, axes = plt.subplots(1, 2, figsize=(14, 7))
modelos = ["Hedônico", "LightGBM"]
cod_vals = [holdout_hed["COD_mediano"], holdout_lgb["COD_mediano"]]
razao_vals = [holdout_hed["razao_mediana"], holdout_lgb["razao_mediana"]]
cores = [COR_HED, COR_LGB]

axes[0].bar(modelos, cod_vals, color=cores)
axes[0].axhline(15, color="gray", linestyle="--", linewidth=1)
axes[0].set_ylabel("COD mediano (%)")
axes[0].set_title("COD no teste final (holdout)")
for i, v in enumerate(cod_vals):
    axes[0].text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=17)
axes[0].spines[["top", "right"]].set_visible(False)

axes[1].bar(modelos, razao_vals, color=cores)
axes[1].axhspan(0.90, 1.10, color="gray", alpha=0.15)
axes[1].set_ylabel("Razão mediana")
axes[1].set_title("Nível geral no teste final (holdout)")
axes[1].set_ylim(0, 1.15)
for i, v in enumerate(razao_vals):
    axes[1].text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=17)
axes[1].spines[["top", "right"]].set_visible(False)

fig.tight_layout()
fig.savefig(SAIDA / "comparativo_holdout.png", dpi=200)
plt.close(fig)

# --- Grafico 4: confianca x sinalizados (destaque no nivel decidido) ---
niveis = [c["confianca"] * 100 for c in conf]
sinalizados_pct = [c["pct_sinalizados"] for c in conf]
decididos = [bool(c.get("nivel_decidido_pela_equipe")) for c in conf]

fig, ax = plt.subplots(figsize=(13, 7.3))
ax.plot(niveis, sinalizados_pct, marker="o", markersize=9, linewidth=2.5, color=COR_LGB)
for x, y, dec in zip(niveis, sinalizados_pct, decididos):
    if dec:
        ax.plot([x], [y], marker="o", markersize=16, markerfacecolor="none",
                markeredgecolor=COR_HED, markeredgewidth=3)
        ax.annotate(f"{y:.1f}%\n(decidido)", (x, y), textcoords="offset points",
                    xytext=(0, 14), ha="center", fontsize=16, color=COR_HED, fontweight="bold")
    else:
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=16)
ax.set_xlabel("Nível de confiança do intervalo de predição")
ax.set_ylabel("Contribuintes sinalizados (%)")
ax.set_title("Confiança × contribuintes sinalizados (teste final)")
ax.invert_xaxis()
ax.set_xticks(niveis)
ax.set_xticklabels([f"{n:.0f}%" for n in niveis])
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "confianca_sinalizados.png", dpi=200)
plt.close(fig)

# --- Grafico 5: GridSearch multi-modelo (MAE por candidato) ---
NOMES_AMIGAVEIS = {
    "lightgbm": "LightGBM",
    "hist_gradient_boosting": "HistGradient\nBoosting",
    "random_forest": "Floresta\nAleatória",
    "extra_trees": "Extra Trees",
    "elasticnet": "ElasticNet\n(linear)",
}
gsm = cv.get("gridsearch_multimodelo", {})
if gsm:
    ordem = sorted(gsm, key=lambda n: gsm[n]["mae_log_cv"])
    nomes = [NOMES_AMIGAVEIS.get(n, n) for n in ordem]
    maes = [gsm[n]["mae_log_cv"] for n in ordem]
    cores_barras = [COR_LGB if i == 0 else COR_HED for i in range(len(ordem))]

    fig, ax = plt.subplots(figsize=(13, 7.3))
    ax.bar(nomes, maes, color=cores_barras)
    for i, v in enumerate(maes):
        ax.text(i, v + 0.001, f"{v:.4f}", ha="center", fontsize=16)
    ax.set_ylabel("Erro absoluto médio (log do valor) — menor é melhor")
    ax.set_title("GridSearch multi-modelo — disputa entre candidatos (CV interna k=5)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(SAIDA / "gridsearch_multimodelo.png", dpi=200)
    plt.close(fig)

print("Graficos salvos em:", SAIDA)
for p in sorted(SAIDA.glob("*.png")):
    print(" -", p.name)
