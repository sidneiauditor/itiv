# -*- coding: utf-8 -*-
"""METRICAS IAAO POR DECIL — COD, PRD e PRB por faixa de valor de venda.

Para que serve: as metricas agregadas escondem ONDE a distorcao mora. Este
script calcula as metricas do estudo de razoes (IBAPE 7.8.1 / IAAO) dentro de
cada decil (fatia de 10%) do valor de venda, mostrando em que faixa de preco o
avaliador erra mais e em que direcao.

Uso:
  python metricas_iaao_por_decil.py                       -> demonstracao com o
      VALOR VENAL atual (VLVENALCADASTRO) sobre os apartamentos do teste.
  python metricas_iaao_por_decil.py arq.parquet AVAL PRECO -> qualquer arquivo
      com uma coluna de avaliacao e uma de preco (ex.: previsoes do modelo
      novo apos a Etapa 4).

Metricas (razao R = avaliacao / preco de venda):
  Mediana da razao  — nivel geral da faixa (meta 0,90-1,10)
  COD               — dispersao media em torno da mediana (meta <= 15%)
  COD mediano       — versao robusta (nao explode com vendas simbolicas)
  PRD               — media das razoes / razao ponderada (meta 0,98-1,03)
  PRB (global)      — inclinacao da distorcao por valor (meta -0,05 a +0,05)

IMPORTANTE: nenhuma linha e' excluida (sem corte sem decisao da equipe).
Vendas simbolicas (R$ 0,01) documentadas na Etapa 2 permanecem e afetam as
metricas baseadas em MEDIA no 1o decil — por isso a coluna robusta existe.
"""
import sys
import numpy as np
import pandas as pd

PASTA = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV"


def metricas_razao(av: np.ndarray, sp: np.ndarray) -> dict:
    """COD, PRD e mediana da razao para um vetor de avaliacoes e precos."""
    r = av / sp
    med = np.median(r)
    cod = 100.0 * np.mean(np.abs(r - med)) / med if med != 0 else np.nan
    cod_rob = 100.0 * np.median(np.abs(r - med)) / med if med != 0 else np.nan
    prd = r.mean() / (av.sum() / sp.sum())
    return {"n": len(r), "razao_mediana": med, "COD": cod, "COD_mediano": cod_rob, "PRD": prd}


def prb_global(av: np.ndarray, sp: np.ndarray) -> float:
    """PRB (IAAO): inclinacao da razao normalizada sobre o log do valor proxy."""
    r = av / sp
    med = np.median(r)
    if med == 0:
        return np.nan
    proxy = 0.5 * sp + 0.5 * av / med
    x = np.log(proxy) / np.log(2)
    y = (r - med) / med
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(beta[1])


def tabela_por_decil(df: pd.DataFrame, col_aval: str, col_preco: str) -> None:
    av = pd.to_numeric(df[col_aval], errors="coerce")
    sp = pd.to_numeric(df[col_preco], errors="coerce")
    m = (av > 0) & (sp > 0)
    av, sp = av[m].to_numpy(float), sp[m].to_numpy(float)
    print(f"Pares validos (avaliacao > 0 e preco > 0): {len(av):,}")

    # deciles do preco de venda
    bordas = np.quantile(sp, np.linspace(0, 1, 11))
    decil = np.clip(np.searchsorted(bordas, sp, side="right") - 1, 0, 9)

    print(f"\n{'decil':>5s} {'faixa de preco (R$)':>28s} {'n':>7s} {'razao_med':>9s} {'COD%':>10s} {'CODmed%':>8s} {'PRD':>7s}")
    for d in range(10):
        sel = decil == d
        if sel.sum() < 2:
            continue
        met = metricas_razao(av[sel], sp[sel])
        faixa = f"{bordas[d]:>11,.0f} a {bordas[d+1]:>11,.0f}"
        print(f"{d+1:>5d} {faixa:>28s} {met['n']:>7,} {met['razao_mediana']:>9.3f} "
              f"{met['COD']:>10.1f} {met['COD_mediano']:>8.1f} {met['PRD']:>7.3f}")

    total = metricas_razao(av, sp)
    prb = prb_global(av, sp)
    print(f"\n{'GERAL':>5s} {'':>28s} {total['n']:>7,} {total['razao_mediana']:>9.3f} "
          f"{total['COD']:>10.1f} {total['COD_mediano']:>8.1f} {total['PRD']:>7.3f}")
    print(f"\nPRB global: {prb:+.4f}  (meta IAAO: -0,05 a +0,05; negativo = "
          "imoveis caros avaliados proporcionalmente mais baixo)")
    print("\nMetas IAAO: razao 0,90-1,10 | COD <= 15% | PRD 0,98-1,03")
    print("(Nenhuma linha foi excluida — vendas simbolicas afetam medias no 1o decil.)")


if __name__ == "__main__":
    if len(sys.argv) == 4:
        arq, col_aval, col_preco = sys.argv[1], sys.argv[2], sys.argv[3]
        df = pd.read_parquet(arq)
        print(f"Arquivo: {arq}\nAvaliacao: {col_aval} | Preco: {col_preco}\n")
    else:
        arq = rf"{PASTA}\amostras\teste.parquet"
        df = pd.read_parquet(arq)
        df = df[df["DSSUBUNIDADE"] == "Apartamento"]
        col_aval, col_preco = "VLVENALCADASTRO", "VLTRANSACAO"
        print("DEMONSTRACAO — valor venal ATUAL x preco de venda "
              "(apartamentos do conjunto de teste)\n"
              "Apos a Etapa 4, rode com as previsoes do modelo novo:\n"
              "  python metricas_iaao_por_decil.py previsoes.parquet VALOR_PREVISTO VLTRANSACAO\n")
    tabela_por_decil(df, col_aval, col_preco)
