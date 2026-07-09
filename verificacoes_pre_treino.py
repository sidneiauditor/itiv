# -*- coding: utf-8 -*-
"""TRAVAS PRE-TREINO — verificacoes automaticas que BLOQUEIAM o treino se falharem.

Roda ANTES de qualquer treino (Etapa 4). Se qualquer verificacao falhar,
o script termina com codigo de erro 1 e o treino NAO deve prosseguir.
NAO altera nenhum dado — apenas verifica.

Verificacoes:
  T1. Os tres arquivos de amostra existem (treino/validacao/teste).
  T2. SQTRANSMISSAO e' unico dentro de cada arquivo.
  T3. Nenhum SQTRANSMISSAO aparece em mais de um arquivo (sem sobreposicao).
  T4. Soma das linhas dos tres arquivos = linhas da base limpa.
  T5. Duplicatas inscricao+data+valor dentro do TREINO: cada venda deve ser
      contada UMA vez (recomendacao tecnica registrada em 22/06/2026,
      pendente de confirmacao da equipe — ver REGISTRO_ETAPAS_APROVACAO).
      Enquanto a deduplicacao nao for aplicada, esta trava FALHA de proposito:
      ela existe para impedir treino com venda repetida sem decisao formal.

Fundamento: Parecer Tecnico de Riscos (Riscos 3, 5 e 6) — transformar regras
textuais em travas de codigo.
"""
import sys
import pandas as pd

PASTA = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV"
BASE = rf"{PASTA}\base_limpa_normas.parquet"
AMOSTRAS = {
    "treino": rf"{PASTA}\amostras\treino.parquet",
    "validacao": rf"{PASTA}\amostras\validacao.parquet",
    "teste": rf"{PASTA}\amostras\teste.parquet",
}
CHAVE_DUP = ["CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO"]

falhas = []
avisos = []

def ok(msg):
    print(f"  [OK]    {msg}")

def falha(msg):
    print(f"  [FALHA] {msg}")
    falhas.append(msg)

print("=" * 70)
print("TRAVAS PRE-TREINO — modelo de apartamentos (ITIV)")
print("=" * 70)

# T1 — arquivos existem
print("\nT1. Arquivos de amostra")
dfs = {}
for nome, arq in AMOSTRAS.items():
    try:
        dfs[nome] = pd.read_parquet(arq)
        ok(f"{nome}: {len(dfs[nome]):,} linhas")
    except Exception as e:
        falha(f"{nome}: nao foi possivel ler ({e})")

if len(dfs) == 3:
    # T2 — ID unico dentro de cada arquivo
    print("\nT2. SQTRANSMISSAO unico dentro de cada arquivo")
    for nome, d in dfs.items():
        ndup = d["SQTRANSMISSAO"].duplicated().sum()
        if ndup == 0:
            ok(f"{nome}: sem ID repetido")
        else:
            falha(f"{nome}: {ndup} SQTRANSMISSAO repetidos (duplicata nao resolvida)")

    # T3 — sem sobreposicao entre arquivos
    print("\nT3. Sem sobreposicao de IDs entre treino/validacao/teste")
    ids = {nome: set(d["SQTRANSMISSAO"]) for nome, d in dfs.items()}
    pares = [("treino", "validacao"), ("treino", "teste"), ("validacao", "teste")]
    for a, b in pares:
        inter = ids[a] & ids[b]
        if not inter:
            ok(f"{a} x {b}: nenhum ID em comum")
        else:
            falha(f"{a} x {b}: {len(inter)} IDs em comum (vazamento!) ex.: {list(inter)[:3]}")

    # T4 — soma bate com a base
    print("\nT4. Soma das amostras = base limpa")
    try:
        n_base = len(pd.read_parquet(BASE, columns=["SQTRANSMISSAO"]))
        n_soma = sum(len(d) for d in dfs.values())
        if n_base == n_soma:
            ok(f"{n_soma:,} = {n_base:,}")
        else:
            falha(f"soma das amostras ({n_soma:,}) != base limpa ({n_base:,})")
    except Exception as e:
        falha(f"nao foi possivel ler a base limpa ({e})")

    # T5 — deduplicacao inscricao+data+valor no TREINO
    print("\nT5. Deduplicacao inscricao+data+valor no TREINO")
    tr = dfs.get("treino")
    if tr is not None and all(c in tr.columns for c in CHAVE_DUP):
        dup_mask = tr.duplicated(subset=CHAVE_DUP, keep="first")
        ndup = int(dup_mask.sum())
        if ndup == 0:
            ok("cada venda (inscricao+data+valor) aparece uma unica vez no treino")
        else:
            falha(
                f"{ndup:,} linhas repetidas (mesma inscricao+data+valor) no treino. "
                "A recomendacao tecnica (22/06/2026, pendente de confirmacao da equipe) "
                "e' contar cada venda UMA vez no treino. Aplicar a deduplicacao no "
                "arquivo de treino (mantendo a base completa intacta) antes de treinar."
            )
    else:
        falha("colunas da chave de duplicata ausentes no treino")

# Lembretes que dependem do codigo de treino (nao verificaveis aqui)
print("\nChecklist adicional para o codigo de treino (Etapa 4):")
print("  - Chauvenet/limites: aplicar SOMENTE no treino (IBAPE 7.6.7/7.9.1)")
print("  - Proxy KNN: vizinhos SEMPRE e apenas do conjunto de treino")
print("  - Registrar semente, versao do codigo e manifesto (gerar_manifesto_treino.py)")

print("\n" + "=" * 70)
if falhas:
    print(f"RESULTADO: BLOQUEADO — {len(falhas)} verificacao(oes) falharam. NAO TREINAR.")
    for f in falhas:
        print(f"  - {f}")
    sys.exit(1)
print("RESULTADO: LIBERADO — todas as travas passaram.")
sys.exit(0)
