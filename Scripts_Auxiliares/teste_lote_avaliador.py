# -*- coding: utf-8 -*-
"""Teste em lote: pega uma amostra de imoveis da planilha e roda no avaliador."""
import re
import sys
import urllib.request
import urllib.parse
import pandas as pd

PLAN = "Imóveis por Setor Fiscal.xlsx"
BASE = "http://localhost:8765/avaliar?q="
N = 40

df = pd.read_excel(PLAN, sheet_name="Exportar Planilha", usecols=["IMOVEL", "DSSETORFISCAL", "VL_VENAL"])
df = df.dropna(subset=["IMOVEL"])
amostra = df.sample(n=N, random_state=42)

re_val = re.compile(r"Valor estimado:\s*<strong>([^<]+)</strong>")
re_pilha = re.compile(r"class='pilha'[^>]*>([^<]+)<")

linhas = []
for _, r in amostra.iterrows():
    insc = int(r["IMOVEL"])
    try:
        with urllib.request.urlopen(BASE + str(insc), timeout=60) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception as e:
        linhas.append((insc, r["DSSETORFISCAL"], r["VL_VENAL"], "ERRO HTTP", str(e)[:40]))
        continue

    if "Nenhum SQ nem inscricao" in html:
        status = "sem transmissao na base"
        est = ""
    elif "transmissoes — escolha uma" in html:
        status = "varias transmissoes"
        est = ""
    elif "nao encontrado na base" in html or "class='erro'" in html or 'class="erro"' in html:
        status = "erro/sem dados"
        est = ""
    else:
        m = re_val.search(html)
        est = m.group(1).strip() if m else "(valor nao extraido)"
        status = "AVALIADO"
    linhas.append((insc, r["DSSETORFISCAL"], r["VL_VENAL"], status, est))

out = pd.DataFrame(linhas, columns=["Inscricao", "Setor", "VL_Venal_planilha", "Resultado", "Valor_estimado_modelo"])
out.to_excel("teste_lote_resultado.xlsx", index=False)

print("=== RESUMO ===")
print(out["Resultado"].value_counts().to_string())
print()
print("=== AVALIADOS ===")
av = out[out["Resultado"] == "AVALIADO"]
print(av.to_string(index=False) if not av.empty else "(nenhum avaliado nesta amostra)")
print()
print("Planilha completa salva em: teste_lote_resultado.xlsx")
