# -*- coding: utf-8 -*-
"""ETAPA 4.2 — Engenharia dos parametros finais do modelo de apartamentos,
conforme Lista_Final_Parametros_Apartamentos.docx (aprovada em 09/07/2026).

ENTRAM: area privativa (log), no de pavimentos do predio, localizacao
(setor fiscal + coordenadas), andar da unidade (+ flag de ausencia).
SAEM: area construida/construida da unidade (redundantes), fatores VLFC*
(circularidade com o valor venal atual), idade (sem dado).

Uso como modulo (import) ou script (roda sobre pool_treino e teste_final e
salva as versoes com os parametros prontos).
"""
import numpy as np
import pandas as pd

COLUNAS_FINAIS = [
    "SQTRANSMISSAO", "CDINSCRICAOIMOB", "DATA_TRANSACAO",
    "VLTRANSACAO", "VLTRANSACAO_DEFLACIONADO", "VAR_TENDENCIA",
    "LOG_AREA", "NUPAVIMENTOS", "CDSETORFISCAL", "VLCOORDGEOX", "VLCOORDGEOY",
    "ANDAR_UNIDADE", "FLAG_ANDAR_AUSENTE",
    "VLVENALCADASTRO",  # mantido so para comparacao (nao entra como preditor)
]


def preparar_parametros(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    area = pd.to_numeric(df["VLAREAUSOPRIV"], errors="coerce")
    tem_area = area > 0
    df["LOG_AREA"] = np.where(tem_area, np.log(area.where(tem_area)), np.nan)

    pav = pd.to_numeric(df["NUPAVIMENTOS"], errors="coerce")
    df["NUPAVIMENTOS"] = pav.where(pav > 0)  # 0/negativo tratado como ausente

    andar = pd.to_numeric(df["NUPAVIMENTOUNIDADE"], errors="coerce")
    df["FLAG_ANDAR_AUSENTE"] = (andar.isna() | (andar <= 0)).astype(int)
    df["ANDAR_UNIDADE"] = andar.where(andar > 0, 0)  # 0 = "sem informacao" (flag indica)

    df["CDSETORFISCAL"] = df["CDSETORFISCAL"]
    df["VLCOORDGEOX"] = pd.to_numeric(df["VLCOORDGEOX"], errors="coerce")
    df["VLCOORDGEOY"] = pd.to_numeric(df["VLCOORDGEOY"], errors="coerce")

    antes = len(df)
    df = df[df["LOG_AREA"].notna()].copy()
    removidos = antes - len(df)
    if removidos:
        print(f"  removidos {removidos} sem area privativa valida "
              "(nao ha como calcular LOG_AREA)")

    return df[COLUNAS_FINAIS]


if __name__ == "__main__":
    from pathlib import Path
    PASTA = Path(r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV") / "amostras"

    print("=" * 70)
    print("ETAPA 4.2 — Engenharia de parametros (Lista Final aprovada)")
    print("=" * 70)

    for nome in ["pool_treino", "teste_final"]:
        print(f"\n{nome}:")
        df = pd.read_parquet(PASTA / f"{nome}.parquet")
        n0 = len(df)
        out = preparar_parametros(df)
        print(f"  {n0:,} -> {len(out):,} linhas")
        out.to_parquet(PASTA / f"{nome}_parametros.parquet", index=False)
        print(f"  salvo: {nome}_parametros.parquet")

    print("\n" + "=" * 70)
    print("Colunas finais:", COLUNAS_FINAIS)
