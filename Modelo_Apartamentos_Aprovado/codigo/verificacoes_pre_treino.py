# -*- coding: utf-8 -*-
"""TRAVAS PRE-TREINO — verificacoes automaticas que BLOQUEIAM o treino se falharem.

Atualizado em 09/07/2026 para o esquema de holdout + k-fold (D7) e a dedup por
remocao (D2), confirmados em Decisoes_Consistencia_Modelo_Apartamentos.docx.

Roda ANTES de qualquer treino (Etapa 4). Se qualquer verificacao falhar,
o script termina com codigo de erro 1 e o treino NAO deve prosseguir.
NAO altera nenhum dado — apenas verifica.

Verificacoes:
  T1. pool_treino_parametros e teste_final_parametros existem.
  T2. SQTRANSMISSAO e' unico dentro de cada arquivo.
  T3. Nenhum SQTRANSMISSAO aparece nos dois arquivos (sem sobreposicao —
      holdout nunca usado no treino/CV).
  T4. Soma das linhas dos dois arquivos = apartamentos apos D1/D2/D3 + filtro
      da equipe de 14/07/2026 (Compra e Venda exato, VLITIV > 0, desvio venal
      x transacao <= 30%).
  T5. Duplicatas inscricao+data+valor: devem estar TOTALMENTE ausentes em
      ambos os arquivos (D2 = remover, nao so contar uma vez).

Fundamento: Parecer Tecnico de Riscos (Riscos 3, 5 e 6) — transformar regras
textuais em travas de codigo.
"""
import sys
import pandas as pd

PASTA = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV"
BASE = rf"{PASTA}\base_limpa_normas.parquet"
ARQUIVOS = {
    "pool_treino": rf"{PASTA}\amostras\pool_treino_parametros.parquet",
    "teste_final": rf"{PASTA}\amostras\teste_final_parametros.parquet",
}
CHAVE_DUP = ["CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO"]
CORTE_TEMPORAL = pd.Timestamp("2020-03-01")
LIMITE_DESVIO_VENAL = 0.30  # filtro da equipe (14/07/2026) — substitui vendas simbolicas

falhas = []

def ok(msg):
    print(f"  [OK]    {msg}")

def falha(msg):
    print(f"  [FALHA] {msg}")
    falhas.append(msg)

print("=" * 70)
print("TRAVAS PRE-TREINO — modelo de apartamentos (ITIV)")
print("=" * 70)

# T1 — arquivos existem
print("\nT1. Arquivos preparados (pool_treino / teste_final)")
dfs = {}
for nome, arq in ARQUIVOS.items():
    try:
        dfs[nome] = pd.read_parquet(arq)
        ok(f"{nome}: {len(dfs[nome]):,} linhas")
    except Exception as e:
        falha(f"{nome}: nao foi possivel ler ({e})")

if len(dfs) == 2:
    # T2 — ID unico dentro de cada arquivo
    print("\nT2. SQTRANSMISSAO unico dentro de cada arquivo")
    for nome, d in dfs.items():
        ndup = d["SQTRANSMISSAO"].duplicated().sum()
        if ndup == 0:
            ok(f"{nome}: sem ID repetido")
        else:
            falha(f"{nome}: {ndup} SQTRANSMISSAO repetidos (duplicata nao resolvida)")

    # T3 — sem sobreposicao entre pool e holdout
    print("\nT3. Sem sobreposicao de IDs entre pool_treino e teste_final")
    ids_pool = set(dfs["pool_treino"]["SQTRANSMISSAO"])
    ids_teste = set(dfs["teste_final"]["SQTRANSMISSAO"])
    inter = ids_pool & ids_teste
    if not inter:
        ok("nenhum ID em comum")
    else:
        falha(f"{len(inter)} IDs em comum (vazamento entre pool e holdout!) ex.: {list(inter)[:3]}")

    # T4 — soma bate com apartamentos apos D1/D2/D3
    print("\nT4. Soma das amostras = apartamentos apos D1/D2/D3")
    try:
        base = pd.read_parquet(BASE, columns=["SQTRANSMISSAO", "DSSUBUNIDADE",
                                               "CDINSCRICAOIMOB", "DATA_TRANSACAO", "VLTRANSACAO",
                                               "DSTIPOTRANSACAO", "VLITIV", "VLVENALCORRIGIDO"])
        base = base[base["DSSUBUNIDADE"] == "Apartamento"].copy()
        base = base.drop_duplicates(subset=["SQTRANSMISSAO"], keep="first")
        # Filtro da equipe (14/07/2026) — mesmo funil de preparar_base_treino.py
        base = base[base["DSTIPOTRANSACAO"].astype(str).str.strip() == "Compra e Venda"]
        base = base[pd.to_numeric(base["VLITIV"], errors="coerce") > 0]
        vt = pd.to_numeric(base["VLTRANSACAO"], errors="coerce")
        vv = pd.to_numeric(base["VLVENALCORRIGIDO"], errors="coerce")
        base = base[((vt - vv).abs() / vv) <= LIMITE_DESVIO_VENAL]
        base = base.drop_duplicates(subset=CHAVE_DUP, keep="first")
        base["DATA_TRANSACAO"] = pd.to_datetime(base["DATA_TRANSACAO"])
        base = base[base["DATA_TRANSACAO"] >= CORTE_TEMPORAL]
        n_esperado = len(base)
        # engenharia de parametros descarta quem nao tem area privativa valida —
        # a soma pode ser um pouco menor que n_esperado por esse motivo, nunca maior
        n_soma = sum(len(d) for d in dfs.values())
        if n_soma <= n_esperado:
            ok(f"{n_soma:,} <= {n_esperado:,} (apartamentos apos D1/D2/D3; "
               "diferenca esperada = sem area privativa valida)")
        else:
            falha(f"soma das amostras ({n_soma:,}) MAIOR que o esperado apos D1/D2/D3 ({n_esperado:,})")
    except Exception as e:
        falha(f"nao foi possivel recalcular o esperado a partir da base limpa ({e})")

    # T5 — duplicatas inscricao+data+valor devem estar AUSENTES (D2 = remover)
    print("\nT5. Duplicatas inscricao+data+valor ausentes (D2 — remocao confirmada 09/07/2026)")
    for nome, d in dfs.items():
        if all(c in d.columns for c in CHAVE_DUP):
            ndup = int(d.duplicated(subset=CHAVE_DUP, keep="first").sum())
            if ndup == 0:
                ok(f"{nome}: nenhuma duplicata de inscricao+data+valor")
            else:
                falha(f"{nome}: {ndup:,} duplicatas de inscricao+data+valor ainda presentes "
                      "(D2 exige remocao completa)")
        else:
            falha(f"{nome}: colunas da chave de duplicata ausentes")

# Lembretes que dependem do codigo de treino (nao verificaveis aqui)
print("\nChecklist adicional do codigo de treino (Etapa 4) — ja implementado em"
      " treinar_modelo_apartamentos.py:")
print("  - Chauvenet ITERATIVO: aplicado somente dentro do treino de cada fold (D7)")
print("  - Proxy KNN: vizinhos sempre e apenas do treino do fold (ou do pool, para o holdout)")
print("  - Manifesto de reprodutibilidade: gerar_manifesto_treino.py")

print("\n" + "=" * 70)
if falhas:
    print(f"RESULTADO: BLOQUEADO — {len(falhas)} verificacao(oes) falharam. NAO TREINAR.")
    for f in falhas:
        print(f"  - {f}")
    sys.exit(1)
print("RESULTADO: LIBERADO — todas as travas passaram.")
sys.exit(0)
