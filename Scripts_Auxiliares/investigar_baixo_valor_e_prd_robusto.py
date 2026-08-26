# -*- coding: utf-8 -*-
"""INVESTIGACAO DE VALOR BAIXO E PRD/PRB ROBUSTOS — apoio ao Risco 4.

Duas analises, lado a lado, sem excluir nenhuma linha da base:

1) Lista para inspecao qualitativa dos casos de VLTRANSACAO muito baixo
   (acima de R$ 1,00, ou seja, ja fora das vendas simbolicas de R$ 0,01
   documentadas na Etapa 2) que ainda estao no 1o percentil do conjunto
   de teste. Serve para a equipe abrir caso a caso e decidir o que sao
   (doacao disfarcada, erro de digitacao, fracao ideal, venda legitima
   atipica, etc.) — nenhum corte e sugerido ou aplicado aqui.

2) PRD e PRB calculados de duas formas, "padrao" e "robusta" (media
   aparada / mediana das razoes), reportadas lado a lado para a equipe
   decidir qual versao constar no relatorio de validacao normativa —
   mesmo padrao ja usado na comparacao do split espacial (Risco 5).

IMPORTANTE: nenhuma linha e' excluida da base nem do calculo padrao.
A versao robusta e' reportada ADICIONALMENTE, nao no lugar da padrao.
"""
import numpy as np
import pandas as pd

PASTA = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV"
ARQ_TESTE = rf"{PASTA}\amostras\teste.parquet"
SAIDA_CSV = rf"{PASTA}\investigacao_valor_baixo_teste.csv"


def trimmed_mean(x: np.ndarray, prop: float) -> float:
    xs = np.sort(x)
    k = int(len(xs) * prop)
    if k == 0:
        return xs.mean()
    return xs[k:-k].mean()


def prd_variantes(av: np.ndarray, sp: np.ndarray) -> dict:
    r = av / sp
    razao_ponderada = av.sum() / sp.sum()
    prd_padrao = r.mean() / razao_ponderada
    prd_aparado_5 = trimmed_mean(r, 0.05) / razao_ponderada
    prd_aparado_10 = trimmed_mean(r, 0.10) / razao_ponderada
    prd_mediana = np.median(r) / razao_ponderada
    return {
        "PRD_padrao_media": prd_padrao,
        "PRD_aparado_5pct": prd_aparado_5,
        "PRD_aparado_10pct": prd_aparado_10,
        "PRD_mediana": prd_mediana,
    }


def prb_variante(av: np.ndarray, sp: np.ndarray, usar_mediana_base: bool = True) -> float:
    r = av / sp
    base = np.median(r) if usar_mediana_base else r.mean()
    if base == 0:
        return np.nan
    proxy = 0.5 * sp + 0.5 * av / base
    x = np.log(proxy) / np.log(2)
    y = (r - base) / base
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(beta[1])


def main():
    df = pd.read_parquet(ARQ_TESTE)
    df = df[df["DSSUBUNIDADE"] == "Apartamento"].copy()

    av_col, sp_col = "VLVENALCADASTRO", "VLTRANSACAO"
    df[av_col] = pd.to_numeric(df[av_col], errors="coerce")
    df[sp_col] = pd.to_numeric(df[sp_col], errors="coerce")
    m = (df[av_col] > 0) & (df[sp_col] > 0)
    df = df[m].copy()
    print(f"Pares validos no teste (Apartamento, avaliacao > 0 e preco > 0): {len(df):,}\n")

    # ------------------------------------------------------------------
    # 1) Lista qualitativa — VLTRANSACAO acima de R$ 1,00 e no 1o percentil
    # ------------------------------------------------------------------
    p1 = np.quantile(df[sp_col].to_numpy(float), 0.01)
    faixa = df[(df[sp_col] > 1.00) & (df[sp_col] <= p1)].copy()
    faixa["razao_aval_venda"] = faixa[av_col] / faixa[sp_col]
    faixa = faixa.sort_values(sp_col)

    cols_lista = ["SQTRANSMISSAO", "CDINSCRICAOIMOB", "DATA_TRANSACAO",
                  sp_col, av_col, "razao_aval_venda", "DSTIPOTRANSACAO",
                  "DSTIPOTRANSMITENTE", "DSTIPOADQUIRENTE"]
    cols_lista = [c for c in cols_lista if c in faixa.columns]

    print("=" * 78)
    print("1) CASOS PARA INSPECAO QUALITATIVA (equipe abre caso a caso)")
    print("=" * 78)
    print(f"1o percentil de VLTRANSACAO no teste: R$ {p1:,.2f}")
    print(f"Casos com R$ 1,00 < VLTRANSACAO <= 1o percentil: {len(faixa)}")
    print("Nenhum corte foi aplicado — lista abaixo e' so para revisao manual.\n")
    with pd.option_context("display.max_rows", None, "display.width", 160):
        print(faixa[cols_lista].to_string(index=False))

    faixa[cols_lista].to_csv(SAIDA_CSV, index=False, encoding="utf-8-sig")
    print(f"\nLista completa salva em: {SAIDA_CSV}  (uso interno — nao versionar em repositorio publico)")

    # ------------------------------------------------------------------
    # 2) PRD/PRB padrao x robusto, lado a lado, para o valor venal ATUAL
    # ------------------------------------------------------------------
    av = df[av_col].to_numpy(float)
    sp = df[sp_col].to_numpy(float)

    print("\n" + "=" * 78)
    print("2) PRD — VERSAO PADRAO x VERSOES ROBUSTAS (base inteira, sem corte)")
    print("=" * 78)
    print("Demonstracao com o valor venal ATUAL (VLVENALCADASTRO) sobre o teste.")
    print("Apos a Etapa 4, repetir com as previsoes do modelo novo.\n")

    variantes = prd_variantes(av, sp)
    for nome, valor in variantes.items():
        print(f"  {nome:<20s} {valor:7.3f}")

    prb_padrao = prb_variante(av, sp, usar_mediana_base=True)
    print(f"\n  PRB (base = mediana, padrao IAAO) {prb_padrao:+.4f}")

    print("\nMetas IAAO: PRD 0,98-1,03 | PRB -0,05 a +0,05")
    print("Leitura: se a versao aparada/mediana ficar dentro da meta e a padrao")
    print("nao, a distorcao esta concentrada em poucos casos extremos (provavel")
    print("ligacao com a lista da secao 1). Se todas as versoes ficarem fora da")
    print("meta, a regressividade e' um padrao mais amplo, nao pontual.")


if __name__ == "__main__":
    main()
