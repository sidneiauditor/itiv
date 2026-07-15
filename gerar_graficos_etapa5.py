# -*- coding: utf-8 -*-
"""Gera os gráficos (PNG) do relatório da Etapa 5, a partir de
etapa5_resultados.json e etapa5_dados_graficos.json."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV")
SAIDA = PASTA / "graficos_relatorio"
SAIDA.mkdir(exist_ok=True)

with open(PASTA / "etapa5_resultados.json", encoding="utf-8") as f:
    r = json.load(f)
with open(PASTA / "etapa5_dados_graficos.json", encoding="utf-8") as f:
    g = json.load(f)

COR_HED = "#1A3A5C"
COR_LGB = "#C0392B"
COR_VENAL = "#7F8C8D"
plt.rcParams.update({
    "font.size": 18, "font.family": "sans-serif",
    "axes.titlesize": 20, "axes.labelsize": 18,
    "xtick.labelsize": 16, "ytick.labelsize": 16,
    "legend.fontsize": 16,
})

# --- 1. Histograma dos resíduos padronizados x curva normal ---
resid = np.array(g["resid_pad_hist"])
fig, ax = plt.subplots(figsize=(13, 7.3))
ax.hist(resid, bins=80, range=(-5, 5), density=True, color=COR_HED, alpha=0.75,
        label="Resíduos padronizados do hedônico")
x = np.linspace(-5, 5, 400)
ax.plot(x, np.exp(-x**2 / 2) / np.sqrt(2 * np.pi), color=COR_LGB, linewidth=2.5,
        label="Curva normal padrão")
ax.set_xlabel("Resíduo padronizado")
ax.set_ylabel("Densidade")
ax.set_title("Normalidade dos resíduos (NBR 14653-2, A.2.1.2)")
ax.legend(frameon=False, fontsize=15)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "etapa5_residuos_hist.png", dpi=200)
plt.close(fig)

# --- 2. Resíduos padronizados x valores ajustados (amostra) ---
aj = np.array(g["amostra_ajustados"])
rp = np.array(g["amostra_resid_pad"])
fig, ax = plt.subplots(figsize=(13, 7.3))
ax.scatter(aj, rp, s=8, alpha=0.35, color=COR_HED)
for y, estilo in [(0, "-"), (2, "--"), (-2, "--")]:
    ax.axhline(y, color="gray", linestyle=estilo, linewidth=1)
ax.set_xlabel("Valor ajustado (log do valor deflacionado)")
ax.set_ylabel("Resíduo padronizado")
ax.set_title("Resíduos × valores ajustados (amostra de 5.000 pontos)")
ax.set_ylim(-6, 6)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "etapa5_residuos_ajustados.png", dpi=200)
plt.close(fig)

# --- 3. Equidade vertical: razão mediana por decil ---
decis = r["bloco3_vertical_por_decil"]
labels = [str(d["decil"]) for d in decis]
razoes = [d["razao_mediana"] for d in decis]
fig, ax = plt.subplots(figsize=(13, 7.3))
ax.axhspan(0.90, 1.10, color="gray", alpha=0.15, label="Meta IAAO (0,90–1,10)")
ax.plot(labels, razoes, marker="o", markersize=10, linewidth=2.5, color=COR_LGB)
for xl, y in zip(labels, razoes):
    ax.annotate(f"{y:.3f}", (xl, y), textcoords="offset points", xytext=(0, 12),
                ha="center", fontsize=14)
ax.axhline(1.0, color="gray", linestyle="--", linewidth=1)
ax.set_xlabel("Decil de valor (1 = mais baratos, 10 = mais caros)")
ax.set_ylabel("Razão mediana (avaliação / preço)")
ax.set_title("Equidade vertical — razão por decil de valor (LightGBM, teste final)")
ax.set_ylim(0.85, 1.15)
ax.legend(frameon=False, fontsize=15)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "etapa5_vertical_razao.png", dpi=200)
plt.close(fig)

# --- 4. Equidade vertical: COD por decil ---
cods = [d["COD_iaao_pct"] for d in decis]
fig, ax = plt.subplots(figsize=(13, 7.3))
ax.bar(labels, cods, color=COR_LGB)
ax.axhline(15, color="gray", linestyle="--", linewidth=1.5, label="Meta IAAO (COD ≤ 15%)")
for i, v in enumerate(cods):
    ax.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=14)
ax.set_xlabel("Decil de valor (1 = mais baratos, 10 = mais caros)")
ax.set_ylabel("COD (%)")
ax.set_title("Uniformidade por decil de valor (LightGBM, teste final)")
ax.legend(frameon=False, fontsize=15)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "etapa5_vertical_cod.png", dpi=200)
plt.close(fig)

# --- 5. Comparativo venal x hedônico x LightGBM ---
comp = r["comparacao_venal_modelos"]
nomes = ["Valor venal\n(cadastro)", "Hedônico", "LightGBM"]
chaves = ["valor_venal_cadastro", "hedonico", "lightgbm"]
cores = [COR_VENAL, COR_HED, COR_LGB]
fig, axes = plt.subplots(1, 2, figsize=(14, 7))
razoes_c = [comp[c]["razao_mediana"] for c in chaves]
cods_c = [comp[c]["COD"] for c in chaves]
axes[0].bar(nomes, razoes_c, color=cores)
axes[0].axhspan(0.90, 1.10, color="gray", alpha=0.15)
axes[0].set_ylabel("Razão mediana")
axes[0].set_title("Nível geral (teste final)")
axes[0].set_ylim(0, 1.2)
for i, v in enumerate(razoes_c):
    axes[0].text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=16)
axes[0].spines[["top", "right"]].set_visible(False)
axes[1].bar(nomes, cods_c, color=cores)
axes[1].axhline(15, color="gray", linestyle="--", linewidth=1.5)
axes[1].set_ylabel("COD (%)")
axes[1].set_title("Uniformidade — COD (teste final)")
for i, v in enumerate(cods_c):
    axes[1].text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=16)
axes[1].spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SAIDA / "etapa5_comparativo_venal.png", dpi=200)
plt.close(fig)

print("Gráficos da Etapa 5 salvos em:", SAIDA)
for p in sorted(SAIDA.glob("etapa5_*.png")):
    print(" -", p.name)
