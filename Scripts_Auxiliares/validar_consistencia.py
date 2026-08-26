"""Validacao de consistencia da amostra conforme NBR 14653 — SO MEDE, nao exclui.
Verifica: dados incompletos, valores incompativeis, duplicidades.
Nenhum corte e' aplicado; resultados servem para a equipe decidir.
"""
import pandas as pd
import numpy as np

df = pd.read_parquet(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\base_limpa_normas.parquet")
n = len(df)
print(f"Base limpa: {n:,} transacoes\n")

# Campos essenciais para o modelo
essenciais = {
    "VLTRANSACAO": "preco de venda",
    "VLAREAUSOPRIV": "area privativa",
    "VLAREATERRENO": "area terreno",
    "DSSUBUNIDADE": "tipologia",
    "CDSETORFISCAL": "setor fiscal",
    "VLCOORDGEOX": "coordenada X",
    "VLCOORDGEOY": "coordenada Y",
    "VLVENALCADASTRO": "valor venal cadastro",
    "NUPAVIMENTOS": "pavimentos",
}

print("== 1. DADOS INCOMPLETOS (% faltante por campo essencial) ==")
for col, desc in essenciais.items():
    if col in df.columns:
        falt = df[col].isna().mean() * 100
        print(f"  {desc:24s} ({col:16s}): {falt:5.1f}% faltante")
    else:
        print(f"  {desc:24s} ({col:16s}): COLUNA AUSENTE")

print("\n== 2. VALORES INCOMPATIVEIS (apenas conta — nao exclui) ==")
vl = pd.to_numeric(df["VLTRANSACAO"], errors="coerce")
ap = pd.to_numeric(df.get("VLAREAUSOPRIV"), errors="coerce")
at = pd.to_numeric(df.get("VLAREATERRENO"), errors="coerce")
print(f"  VLTRANSACAO <= 0:              {(vl<=0).sum():,}")
print(f"  Area privativa <= 0 ou nula:  {((ap<=0)|ap.isna()).sum():,}")
print(f"  Area terreno <= 0 ou nula:    {((at<=0)|at.isna()).sum():,}")
# valor/m2 implausivel (so conta, nao corta)
area_mod = ap.where(ap>0, at)
m2 = vl / area_mod
print(f"  R$/m2 calculavel:             {m2.notna().sum():,}")
if m2.notna().any():
    print(f"    min={m2.min():,.0f} | p1={m2.quantile(.01):,.0f} | mediana={m2.median():,.0f} | p99={m2.quantile(.99):,.0f} | max={m2.max():,.0f}")

print("\n== 3. DUPLICIDADES ==")
print(f"  SQTRANSMISSAO repetido:       {df['SQTRANSMISSAO'].duplicated().sum():,}")
# mesma inscricao + mesma data + mesmo valor = possivel duplicata real
chave = ["CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO"]
if all(c in df.columns for c in chave):
    dup = df.duplicated(subset=chave, keep=False)
    print(f"  Mesma inscricao+data+valor:   {dup.sum():,} linhas em {df[dup].groupby(chave).ngroups if dup.any() else 0} grupos")

print("\n(NENHUMA linha foi excluida — apenas medicao.)")
