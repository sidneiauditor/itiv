"""Diagnostico da amostra bruta de transmissoes ITIV — antes de treinar.
Criterios decididos com a equipe (auditor):
  1. Situacao: manter Baixado + Liberado + Em aberto (excluir Cancelado)
  2. Tipo: manter SOMENTE 'Compra e Venda' e 'Compra e venda de garagem'
  3. Datas: recuperar por registro/lavratura/assinatura; descartar so quem nao tem nenhuma
  4. Fracao: medir transmissoes de 100% (escala 0-1, 1.0 = 100%)
NAO treina. NAO aplica limite de area/valor.
"""
import pandas as pd

ARQ = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\Informações ITIV 20260610.xlsx"
cols = [
    "SQTRANSMISSAO", "DSSITUACAOTRANSMISSAO", "DSTIPOTRANSACAO",
    "DTPAGAMENTO", "DTLAVRATURA", "DTREGISTROCARTORIO", "DTASSINATURACONTRATO",
    "VLTRANSACAO", "VLFRACAOTERRENO", "VLFRACAOCONSTRUCAO", "DSSUBUNIDADE",
]
df = pd.read_excel(ARQ, sheet_name="Exportar Planilha", usecols=cols)
n0 = len(df)
print(f"TOTAL BRUTO: {n0:,}\n")

def data_ok(s):
    return pd.to_datetime(s, errors="coerce").between("2004-01-01", "2026-12-31")

# 1. Situacao
sit_ok = df["DSSITUACAOTRANSMISSAO"].isin(["Baixado", "Liberado", "Em aberto"])
print(f"1. Situacao mantida: {sit_ok.sum():,} | removida: {(~sit_ok).sum():,}")

# 2. Tipo — lista de INCLUSAO (so vendas de mercado)
def eh_venda(t):
    if pd.isna(t): return False
    t = str(t).lower()
    return t.startswith("compra e venda") or "compra e venda de garagem" in t
tipo_ok = df["DSTIPOTRANSACAO"].apply(eh_venda)
print(f"2. Tipo mantido (so compra e venda + garagem): {tipo_ok.sum():,} | removido: {(~tipo_ok).sum():,}")
print("   Tipos mantidos:")
print(df.loc[tipo_ok, "DSTIPOTRANSACAO"].value_counts().to_string())

# 3. Datas
dt_pag_ok = data_ok(df["DTPAGAMENTO"])
recup = (~dt_pag_ok) & (data_ok(df["DTREGISTROCARTORIO"]) | data_ok(df["DTLAVRATURA"]) | data_ok(df["DTASSINATURACONTRATO"]))
dt_qualquer = dt_pag_ok | recup
print(f"\n3. Datas: DTPAGAMENTO ok={dt_pag_ok.sum():,} | recuperadas={recup.sum():,} | sem nenhuma={((~dt_qualquer)).sum():,}")

# 4. Fracao (escala 0-1)
ft = pd.to_numeric(df["VLFRACAOTERRENO"], errors="coerce")
fc = pd.to_numeric(df["VLFRACAOCONSTRUCAO"], errors="coerce")
print("\n4. Fracao transmitida (escala 0-1):")
print(f"   VLFRACAOTERRENO == 1,0 (100%): {(ft==1.0).sum():,} | < 1,0: {(ft<1.0).sum():,}")
print(f"   VLFRACAOCONSTRUCAO == 1,0 (100%): {(fc==1.0).sum():,}")
print(f"   Distribuicao terreno:")
print(ft.round(2).value_counts().head(8).to_string())
fracao_100 = (ft == 1.0)

# Combinacao final (com e sem o filtro de fracao 100%, para a equipe decidir)
base = sit_ok & tipo_ok & dt_qualquer
vl_ok = pd.to_numeric(df["VLTRANSACAO"], errors="coerce") > 0
final_sem_fracao = base & vl_ok
final_com_fracao = base & vl_ok & fracao_100
print("\n== AMOSTRA FINAL (SEM limite de area/valor) ==")
print(f"  Sit+Tipo+Data+Valor>0:                 {final_sem_fracao.sum():,}")
print(f"  + fracao terreno 100%:                 {final_com_fracao.sum():,}")
print(f"  ({final_com_fracao.sum()/n0*100:.1f}% do bruto)")
