# Documentação dos filtros — célula de análise ITIV

Célula de referência em `wrangler.ipynb` (cópia de `df` → filtros → diferença venal × transação).

## Visão geral

A análise parte de uma cópia integral de `df` e aplica **quatro condições em sequência**. Só permanecem registros que satisfazem todas elas. Depois o resultado é reduzido às colunas de valor, ordenado pela diferença e formatado como moeda.

---

## Filtro 1 — Tipo de transação

```python
filtro1 = temp['DSTIPOTRANSACAO'].str.strip() == "Compra e Venda"
```

| Aspecto | Detalhe |
|--------|---------|
| Coluna | `DSTIPOTRANSACAO` |
| Critério | Valor igual a `"Compra e Venda"` |
| Tratamento | `.str.strip()` remove espaços no início/fim do texto |
| Efeito | Exclui os demais tipos (adjudicação, doação, etc.) |

---

## Filtro 2 — Subunidade do imóvel

```python
filtro2 = temp['DSSUBUNIDADE'].str.strip() == "Apartamento"
```

| Aspecto | Detalhe |
|--------|---------|
| Coluna | `DSSUBUNIDADE` |
| Critério | Valor igual a `"Apartamento"` |
| Tratamento | `.str.strip()` na comparação |
| Efeito | Mantém apenas unidades classificadas como apartamento |

---

## Filtro 3 — Valor do ITIV

```python
filtro3 = temp['VLITIV'] > 0
```

| Aspecto | Detalhe |
|--------|---------|
| Coluna | `VLITIV` |
| Critério | Valor estritamente maior que zero |
| Efeito | Exclui registros sem ITIV lançado, com ITIV zerado ou negativo |

---

## Combinação dos filtros 1, 2 e 3

```python
temp = temp[filtro1 & filtro2 & filtro3].copy()
```

Os três filtros são aplicados com **E lógico (`&`)**: o registro precisa ser **Compra e Venda**, **Apartamento** e ter **VLITIV > 0**.

---

## Filtro 4 — Proximidade entre valor de transação e valor venal

```python
mask = (abs(temp['VLTRANSACAO'] - temp['VLVENALCORRIGIDO']) / temp['VLVENALCORRIGIDO']) <= 0.3
temp = temp[mask].copy()
```

| Aspecto | Detalhe |
|--------|---------|
| Colunas | `VLTRANSACAO`, `VLVENALCORRIGIDO` |
| Fórmula | \(\lvert V_{transação} - V_{venal}\rvert / V_{venal} \le 0,3\) |
| Limite | **30%** de desvio relativo ao valor venal corrigido |
| Efeito | Descarta casos em que a diferença percentual entre preço declarado e valor venal ultrapassa 30% |

Em outras palavras: ficam só operações em que o valor da transação está relativamente alinhado ao valor venal (dentro de ±30%).

---

## Pós-filtro (transformações, não filtros)

Após os filtros, a célula:

1. Seleciona apenas `VLVENALCORRIGIDO` e `VLTRANSACAO`
2. Cria `DIFF = VLVENALCORRIGIDO - VLTRANSACAO`
3. Ordena por `DIFF` decrescente (maiores diferenças venal − transação primeiro)
4. Formata os três valores como reais (`R$ …`)
5. Imprime a quantidade de transações (`print(temp.shape[0])`)
6. Exibe as 10 primeiras linhas (`head(10)`)

---

## Resumo da população final

Registros que, ao mesmo tempo:

1. São **Compra e Venda**
2. São **Apartamento**
3. Têm **VLITIV > 0**
4. Têm desvio relativo \(\lvert VLTRANSACAO - VLVENALCORRIGIDO\rvert / VLVENALCORRIGIDO \le 30\%\)
