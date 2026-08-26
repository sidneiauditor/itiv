# -*- coding: utf-8 -*-
"""DIAGNOSTICO — Split aleatorio x split espacial por PREDIO (apartamentos).

Pergunta que responde: o sorteio aleatorio esta inflando as metricas por
colocar apartamentos do MESMO PREDIO no treino e no teste ("gemeos")?

Metodo:
  - So apartamentos, da base limpa.
  - "Predio" = mesmo par exato de coordenadas (X, Y). Sem coordenada -> a
    propria transacao vira um bloco isolado (1,6% dos casos; divulgado).
  - Mesmo modelo diagnostico das Etapas 5/7: log(valor) ~ log(area privativa)
    + n. pavimentos + setor fiscal (variaveis indicadoras), por algebra
    matricial (lstsq) — identico ao usado nos documentos aprovados.
  - Dois esquemas de divisao 80/20, mesma semente 42:
      (A) aleatorio por transacao (como a Etapa 1 atual)
      (B) por bloco de predio (o predio inteiro fica de um lado so)
  - Duas variantes de dados:
      (1) todos os dados
      (2) Chauvenet iterativo aplicado SO no treino (NBR 14653-2 B.3,
          um a um a partir do mais distante), em log(R$/m2)
  - Metricas no TESTE (fora da amostra): R2 em log e COD.

DIVULGACAO METODOLOGICA (somente para este diagnostico; nenhum arquivo e'
alterado): as repeticoes de mesma inscricao+data+valor sao contadas UMA vez,
seguindo a recomendacao tecnica de 22/06/2026 (pendente de confirmacao da
equipe). Sem isso, a propria duplicata contaminaria a comparacao entre os
dois esquemas de divisao, misturando dois riscos distintos (Riscos 3 e 5 do
Parecer).

Interpretacao: se (B) der resultado bem pior que (A), o numero de (A) esta
inflado por vazamento espacial e nao representa o desempenho em predios que
o modelo nunca viu. Se derem parecidos, o sorteio aleatorio e' defensavel.
"""
import numpy as np
import pandas as pd
from scipy.special import erfcinv

BASE = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\base_limpa_normas.parquet"
SEMENTE = 42

# ---------------------------------------------------------------- dados
cols = ["SQTRANSMISSAO", "CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO",
        "VLAREAUSOPRIV", "NUPAVIMENTOS", "CDSETORFISCAL", "DSSUBUNIDADE",
        "VLCOORDGEOX", "VLCOORDGEOY"]
df = pd.read_parquet(BASE, columns=cols)
df = df[df["DSSUBUNIDADE"] == "Apartamento"].copy()
n_apt = len(df)

# dedup inscricao+data+valor (SO para o diagnostico — ver docstring)
df = df.drop_duplicates(subset=["CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO"], keep="first")
n_dedup = len(df)

vl = pd.to_numeric(df["VLTRANSACAO"], errors="coerce")
ar = pd.to_numeric(df["VLAREAUSOPRIV"], errors="coerce")
pav = pd.to_numeric(df["NUPAVIMENTOS"], errors="coerce")
setor = df["CDSETORFISCAL"].astype(str)

m = (vl > 0) & (ar > 0) & pav.notna() & df["CDSETORFISCAL"].notna()
df = df[m].copy()
df["_Y"] = np.log(vl[m])
df["_LOGAREA"] = np.log(ar[m])
df["_PAV"] = pav[m]
df["_SETOR"] = setor[m]
df["_LOGM2"] = df["_Y"] - df["_LOGAREA"]

# bloco de predio = par exato (X, Y); sem coordenada -> bloco proprio
tem_xy = df["VLCOORDGEOX"].notna() & df["VLCOORDGEOY"].notna()
df["_PREDIO"] = np.where(
    tem_xy,
    df["VLCOORDGEOX"].astype(str) + "|" + df["VLCOORDGEOY"].astype(str),
    "solo_" + df["SQTRANSMISSAO"].astype(str),
)

print(f"Apartamentos na base limpa:            {n_apt:,}")
print(f"Apos contar cada venda uma vez:        {n_dedup:,}")
print(f"Com area, pavimentos e setor validos:  {len(df):,}")
print(f"Blocos de predio distintos:            {df['_PREDIO'].nunique():,}")
print(f"Sem coordenada (bloco proprio):        {(~tem_xy).sum():,} ({(~tem_xy).mean()*100:.1f}%)")

# ---------------------------------------------------------------- modelo
def ajustar_e_avaliar(treino: pd.DataFrame, teste: pd.DataFrame):
    """OLS log(valor) ~ log(area) + pavimentos + setor (dummies do treino)."""
    setores = sorted(treino["_SETOR"].unique())
    idx = {s: i for i, s in enumerate(setores[1:])}  # 1o setor = referencia

    def matriz(d):
        X = np.zeros((len(d), 2 + len(idx)))
        X[:, 0] = d["_LOGAREA"].to_numpy()
        X[:, 1] = d["_PAV"].to_numpy()
        for j, s in enumerate(d["_SETOR"].to_numpy()):
            k = idx.get(s)
            if k is not None:
                X[j, 2 + k] = 1.0
        return np.column_stack([np.ones(len(d)), X])

    Xt, yt = matriz(treino), treino["_Y"].to_numpy()
    beta, *_ = np.linalg.lstsq(Xt, yt, rcond=None)

    Xs, ys = matriz(teste), teste["_Y"].to_numpy()
    pred = Xs @ beta
    ss_res = float(((ys - pred) ** 2).sum())
    ss_tot = float(((ys - ys.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot

    # Erro percentual mediano (robusto). O COD classico (media) nao e'
    # informativo aqui: o teste cru contem vendas simbolicas (R$ 0,01)
    # ja documentadas na Etapa 2, que explodem qualquer media de razoes.
    # O COD oficial sera medido na Etapa 5, apos as decisoes de saneamento.
    razao = np.exp(pred) / np.exp(ys)          # avaliacao / preco de venda
    med = np.median(razao)
    mdape = 100.0 * np.median(np.abs(razao - med)) / med

    fora = int((~teste["_SETOR"].isin(setores)).sum())
    return r2, mdape, fora

def chauvenet_iterativo(treino: pd.DataFrame) -> pd.DataFrame:
    """Remove discrepantes de log(R$/m2) um a um (NBR 14653-2 B.3)."""
    x = treino["_LOGM2"].to_numpy().copy()
    vivo = np.ones(len(x), dtype=bool)
    while vivo.sum() > 2:
        xa = x[vivo]
        mu, sd = xa.mean(), xa.std(ddof=0)
        if sd == 0:
            break
        thr = np.sqrt(2) * erfcinv(1.0 / (2 * vivo.sum()))
        z = np.abs(x - mu) / sd
        z[~vivo] = -1.0
        pior = int(np.argmax(z))
        if z[pior] > thr:
            vivo[pior] = False
        else:
            break
    return treino[vivo]

# ---------------------------------------------------------------- splits
rng = np.random.default_rng(SEMENTE)

# (A) aleatorio por transacao
perm = rng.permutation(len(df))
corte = int(len(df) * 0.80)
tr_A = df.iloc[perm[:corte]]
te_A = df.iloc[perm[corte:]]

# (B) por bloco de predio (ordena antes p/ sorteio deterministico e seguro)
predios = np.array(sorted(df["_PREDIO"].unique()), dtype=object)
rng2 = np.random.default_rng(SEMENTE)
rng2.shuffle(predios)
tam = df.groupby("_PREDIO").size()
alvo = int(len(df) * 0.80)
acum, treino_pred = 0, set()
for p in predios:
    if acum >= alvo:
        break
    treino_pred.add(p)
    acum += int(tam[p])
tr_B = df[df["_PREDIO"].isin(treino_pred)]
te_B = df[~df["_PREDIO"].isin(treino_pred)]

# ---------------------------------------------------------------- rodadas
print("\n== Resultados no TESTE (fora da amostra) ==")
print(f"{'variante':34s} {'split':22s} {'n_trein':>8s} {'n_teste':>8s} {'R2':>7s} {'ErroMd%':>7s} {'setor_novo':>10s}")
resultados = {}
for rotulo_var, prep in [
    ("todos os dados", lambda t: t),
    ("Chauvenet iterativo (so treino)", chauvenet_iterativo),
]:
    for rotulo_split, (tr, te) in [
        ("(A) aleatorio", (tr_A, te_A)),
        ("(B) bloco de predio", (tr_B, te_B)),
    ]:
        tr_fit = prep(tr)
        r2, cod, fora = ajustar_e_avaliar(tr_fit, te)
        resultados[(rotulo_var, rotulo_split)] = (r2, cod)
        print(f"{rotulo_var:34s} {rotulo_split:22s} {len(tr_fit):>8,} {len(te):>8,} {r2:>7.3f} {cod:>7.1f} {fora:>10,}")

print("\n== Diferenca (A) - (B) — quanto o sorteio aleatorio infla ==")
for var in ["todos os dados", "Chauvenet iterativo (so treino)"]:
    dr2 = resultados[(var, "(A) aleatorio")][0] - resultados[(var, "(B) bloco de predio")][0]
    dmd = resultados[(var, "(B) bloco de predio")][1] - resultados[(var, "(A) aleatorio")][1]
    print(f"  {var:34s}: R2 {dr2:+.3f} | ErroMd {dmd:+.1f} p.p.")

print("\n(Nenhum arquivo foi alterado — diagnostico apenas.)")
