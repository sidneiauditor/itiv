# -*- coding: utf-8 -*-
"""
Adiciona a coluna "STATUS DA AVALIACAO" na planilha
"ITIV_Base_Consolidada_2025_2026 (Filtro).xlsx" (abas "Dados 2025" e
"Dados 2026"), mantendo guias, filtros e formatacao originais.

Classificacao (criterio adotado em 15/07/2026):
  - Compara BASE_INFERIDA (o que foi efetivamente tributado no ITIV) com a
    ESTIMATIVA DO MODELO (LIGHTGBM).
  - Tolerancia de +/-15%, ancorada na propria meta normativa do projeto
    (COD maximo de 15%, padrao IAAO/NBR 14653-2 usado desde a Etapa 5 para
    aprovar o modelo) — evita escolher um numero novo sem lastro normativo.
  - "Compativel": razao entre 0,85 e 1,15.
  - "Necessidade Avaliacao por Auditor": razao fora dessa faixa.
  - "Fora de Escopo do Modelo": linhas sem estimativa do modelo (nao e
    Apartamento, ou nao foi encontrada na base ITIV) — nao classificadas
    como Compativel/Auditor por falta de dado para comparar.

Executar:  python gerar_status_avaliacao.py
Gera:      Modelo_Apartamentos_Aprovado/ITIV_Base_Consolidada_2025_2026 (Filtro) - Status.xlsx
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.filters import FilterColumn, Filters

from metricas_iaao_por_decil import metricas_razao, prb_global

PASTA = Path(__file__).resolve().parent.parent
ARQUIVO_ENTRADA = PASTA / "ITIV_Base_Consolidada_2025_2026 (Filtro).xlsx"
ARQUIVO_SAIDA = PASTA / "ITIV_Base_Consolidada_2025_2026 (Filtro) - Status.xlsx"

TOLERANCIA = 0.15  # +/-15%, ancorado na meta normativa de COD <= 15% (IAAO/NBR 14653-2)
COL_BASE_INFERIDA = 13  # M
COL_ESTIMATIVA_MODELO = 16  # P
LINHA_CABECALHO = 3
PRIMEIRA_LINHA_DADOS = 4

COMPATIVEL = "Compatível"
NECESSITA_AUDITOR = "Necessidade Avaliação por Auditor"
FORA_ESCOPO = "Fora de Escopo do Modelo"

COR_COMPATIVEL = "C6EFCE"
COR_AUDITOR = "FFC7CE"
COR_FORA_ESCOPO = "F2F2F2"
AZUL_HEX = "1A3A5C"


def _fmt_rs(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def classificar(base_inferida, estimativa) -> tuple[str, str]:
    """Retorna (status, justificativa)."""
    if not isinstance(estimativa, (int, float)) or estimativa == 0:
        return FORA_ESCOPO, "Imóvel não é Apartamento com compra e venda registrada, ou não foi localizado na base ITIV — o modelo não gera estimativa para este caso."
    if not isinstance(base_inferida, (int, float)) or base_inferida <= 0:
        return FORA_ESCOPO, "Base tributária (Base_Inferida) ausente ou inválida — não é possível comparar com a estimativa do modelo."

    razao = estimativa / base_inferida
    diferenca_pct = (razao - 1) * 100
    sentido = "acima" if diferenca_pct >= 0 else "abaixo"

    if (1 - TOLERANCIA) <= razao <= (1 + TOLERANCIA):
        justificativa = (
            f"Estimativa do modelo ({_fmt_rs(estimativa)}) está {abs(diferenca_pct):.1f}% {sentido} "
            f"da base tributada ({_fmt_rs(base_inferida)}) — dentro da tolerância de ±{TOLERANCIA*100:.0f}% "
            f"(meta normativa de COD ≤ 15%, IAAO/NBR 14653-2)."
        )
        return COMPATIVEL, justificativa

    justificativa = (
        f"Estimativa do modelo ({_fmt_rs(estimativa)}) está {abs(diferenca_pct):.1f}% {sentido} "
        f"da base tributada ({_fmt_rs(base_inferida)}) — fora da tolerância de ±{TOLERANCIA*100:.0f}%; "
        f"recomenda-se análise individual do auditor fiscal."
    )
    return NECESSITA_AUDITOR, justificativa


def processar_aba(ws) -> None:
    col_status = ws.max_column + 1
    col_justificativa = col_status + 1
    letra_status = get_column_letter(col_status)
    letra_justificativa = get_column_letter(col_justificativa)

    cab_ref = ws.cell(row=LINHA_CABECALHO, column=COL_ESTIMATIVA_MODELO)

    def copiar_estilo_cabecalho(celula):
        if cab_ref.font:
            celula.font = cab_ref.font.copy()
        if cab_ref.fill:
            celula.fill = cab_ref.fill.copy()
        if cab_ref.alignment:
            celula.alignment = cab_ref.alignment.copy()

    ws.cell(row=LINHA_CABECALHO, column=col_status, value="STATUS DA AVALIAÇÃO")
    copiar_estilo_cabecalho(ws.cell(row=LINHA_CABECALHO, column=col_status))
    ws.cell(row=LINHA_CABECALHO, column=col_justificativa, value="JUSTIFICATIVA")
    copiar_estilo_cabecalho(ws.cell(row=LINHA_CABECALHO, column=col_justificativa))

    preenchimentos = {
        COMPATIVEL: PatternFill(start_color=COR_COMPATIVEL, end_color=COR_COMPATIVEL, fill_type="solid"),
        NECESSITA_AUDITOR: PatternFill(start_color=COR_AUDITOR, end_color=COR_AUDITOR, fill_type="solid"),
        FORA_ESCOPO: PatternFill(start_color=COR_FORA_ESCOPO, end_color=COR_FORA_ESCOPO, fill_type="solid"),
    }

    contagem = {COMPATIVEL: 0, NECESSITA_AUDITOR: 0, FORA_ESCOPO: 0}

    for r in range(PRIMEIRA_LINHA_DADOS, ws.max_row + 1):
        base_inferida = ws.cell(row=r, column=COL_BASE_INFERIDA).value
        estimativa = ws.cell(row=r, column=COL_ESTIMATIVA_MODELO).value
        status, justificativa = classificar(base_inferida, estimativa)
        contagem[status] += 1

        celula_status = ws.cell(row=r, column=col_status, value=status)
        celula_status.fill = preenchimentos[status]
        celula_status.alignment = Alignment(horizontal="center")

        celula_just = ws.cell(row=r, column=col_justificativa, value=justificativa)
        celula_just.alignment = Alignment(horizontal="left", wrap_text=True, vertical="top")

    ws.column_dimensions[letra_status].width = 32
    ws.column_dimensions[letra_justificativa].width = 70

    # estende o filtro e a area de dados para incluir as novas colunas
    if ws.auto_filter.ref:
        inicio, _ = ws.auto_filter.ref.split(":")
        col_letra_inicio = "".join(ch for ch in inicio if ch.isalpha())
        ws.auto_filter.ref = f"{col_letra_inicio}{LINHA_CABECALHO}:{letra_justificativa}{ws.max_row}"

    print(f"  {ws.title}: {contagem}")


def _coletar_pares(ws) -> tuple[np.ndarray, np.ndarray]:
    """Pares (estimativa, base_inferida) validos, restritos a 'Compra e Venda'
    (qualquer subtipo) — a populacao correta para um estudo de razoes IAAO.
    Exclui transacoes de natureza diferente (incorporacao, doacao, permuta
    etc.), cujo valor nao representa um preco de mercado comparavel, e que
    distorcem violentamente COD/PRD baseados em media (ja documentado em
    metricas_iaao_por_decil.py)."""
    av, sp = [], []
    for r in range(PRIMEIRA_LINHA_DADOS, ws.max_row + 1):
        tipo = str(ws.cell(row=r, column=3).value or "")
        if not tipo.startswith("Compra e Venda"):
            continue
        estimativa = ws.cell(row=r, column=COL_ESTIMATIVA_MODELO).value
        base_inferida = ws.cell(row=r, column=COL_BASE_INFERIDA).value
        if not isinstance(estimativa, (int, float)) or estimativa <= 0:
            continue
        if not isinstance(base_inferida, (int, float)) or base_inferida <= 0:
            continue
        av.append(float(estimativa))
        sp.append(float(base_inferida))
    return np.array(av), np.array(sp)


def montar_aba_indicadores(wb, abas_por_ano: dict) -> None:
    linhas = []
    todos_av, todos_sp = [], []
    for nome, ws in abas_por_ano.items():
        av, sp = _coletar_pares(ws)
        todos_av.append(av)
        todos_sp.append(sp)
        met = metricas_razao(av, sp)
        prb = prb_global(av, sp)
        linhas.append((nome, met, prb))

    av_total = np.concatenate(todos_av)
    sp_total = np.concatenate(todos_sp)
    met_total = metricas_razao(av_total, sp_total)
    prb_total = prb_global(av_total, sp_total)
    linhas.append(("Total (2025+2026)", met_total, prb_total))

    ws = wb.create_sheet("Indicadores IAAO (Modelo)")
    titulo = ws.cell(row=1, column=1, value="Indicadores IAAO — Estimativa do modelo (LightGBM) x Base Tributada (Base_Inferida)")
    titulo.font = Font(bold=True, size=13, color=AZUL_HEX)
    ws.cell(row=2, column=1, value=(
        "Restrito a transacoes de 'Compra e Venda' (qualquer subtipo) — populacao correta para um "
        "estudo de razoes; exclui incorporacao/doacao/permuta, cujo valor nao representa preco de mercado."
    )).font = Font(italic=True, size=9, color="666666")

    cabecalho = ["Recorte", "n", "Razão mediana", "COD (média, %)", "COD (mediano, %)", "PRD", "PRB",
                 "Meta IAAO"]
    linha_cab = 4
    for c, texto in enumerate(cabecalho, start=1):
        cel = ws.cell(row=linha_cab, column=c, value=texto)
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = PatternFill(start_color=AZUL_HEX, end_color=AZUL_HEX, fill_type="solid")
        cel.alignment = Alignment(horizontal="center")

    meta_combinada = "Razão 0,98–1,03 | COD ≤15% | PRD 0,98–1,03 | PRB -0,05–0,05"

    for i, (nome, met, prb) in enumerate(linhas):
        r = linha_cab + 1 + i
        valores = [nome, met["n"], round(met["razao_mediana"], 3), round(met["COD"], 1),
                   round(met["COD_mediano"], 1), round(met["PRD"], 3), round(prb, 3), meta_combinada]
        for c, v in enumerate(valores, start=1):
            cel = ws.cell(row=r, column=c, value=v)
            cel.alignment = Alignment(horizontal="left" if c in (1, 8) else "center")
            if i == len(linhas) - 1:
                cel.font = Font(bold=True)

    larguras = [22, 8, 14, 16, 18, 8, 8, 50]
    for c, largura in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(c)].width = largura

    nota = ws.cell(row=linha_cab + len(linhas) + 2, column=1, value=(
        "COD (média) é sensível a poucos casos extremos (ex.: bases tributárias simbólicas em "
        "'Compra e Venda — base inferior ao VVA'); use o COD (mediano) como referência mais robusta."
    ))
    nota.font = Font(italic=True, size=9, color="666666")

    # ------------------------------------------------------------------
    # Explicacao em linguagem simples, para quem nao e da area tecnica
    # ------------------------------------------------------------------
    linha_exp = linha_cab + len(linhas) + 4
    titulo_exp = ws.cell(row=linha_exp, column=1, value="O que significam esses indicadores (em palavras simples)")
    titulo_exp.font = Font(bold=True, size=12, color=AZUL_HEX)

    explicacoes = [
        ("COD — Coeficiente de Dispersão",
         "Mede o quanto as avaliações do modelo variam de um imóvel para outro, para mais ou para "
         "menos, em relação ao valor típico. É como perguntar: \"o modelo erra sempre um pouco igual, "
         "ou às vezes acerta bem e às vezes erra feio?\". Quanto MENOR o COD, mais consistente e "
         "confiável é o modelo. A referência aceita para imóveis residenciais é até 15%."),
        ("PRD — Price-Related Differential",
         "Verifica se o modelo trata melhor os imóveis baratos do que os caros, ou vice-versa. Em "
         "outras palavras: \"o modelo é mais generoso com imóvel barato e mais rígido com imóvel caro "
         "(ou o contrário)?\". O valor ideal é próximo de 1,0 (entre 0,98 e 1,03) — significa que o "
         "modelo trata os dois grupos de forma equilibrada."),
        ("PRB — Price-Related Bias",
         "Mede a mesma ideia do PRD (se o modelo favorece imóveis baratos ou caros), mas de um jeito "
         "estatisticamente mais confiável e menos sensível a casos isolados fora da curva. O valor "
         "ideal fica entre -0,05 e +0,05: perto de zero significa que não há favorecimento por faixa "
         "de preço."),
        ("Razão mediana",
         "Compara, no meio da distribuição, quanto o modelo estima em relação ao valor real (aqui, a "
         "base tributada). Se for 1,0, o modelo acerta em cheio na mediana; acima de 1,0, o modelo "
         "tende a estimar valores maiores; abaixo de 1,0, valores menores."),
    ]

    r = linha_exp + 1
    for nome_ind, texto in explicacoes:
        cel_nome = ws.cell(row=r, column=1, value=nome_ind)
        cel_nome.font = Font(bold=True, color=AZUL_HEX)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        r += 1
        cel_txt = ws.cell(row=r, column=1, value=texto)
        cel_txt.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        ws.row_dimensions[r].height = 48
        r += 2

    print("\nIndicadores IAAO (Modelo):")
    for nome, met, prb in linhas:
        print(f"  {nome}: n={met['n']} razao_med={met['razao_mediana']:.3f} "
              f"COD_med={met['COD_mediano']:.1f}% PRD={met['PRD']:.3f} PRB={prb:.3f}")


def main() -> None:
    print(f"Carregando {ARQUIVO_ENTRADA.name}...")
    wb = openpyxl.load_workbook(ARQUIVO_ENTRADA)

    abas_por_ano = {}
    for nome_aba in ["Dados 2025", "Dados 2026"]:
        print(f"Processando {nome_aba}...")
        processar_aba(wb[nome_aba])
        abas_por_ano[nome_aba.replace("Dados ", "")] = wb[nome_aba]

    montar_aba_indicadores(wb, abas_por_ano)

    wb.save(ARQUIVO_SAIDA)
    print(f"\nPronto: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
