# Projeto — Adequação do Avaliador ITIV às Normas Técnicas

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**
**Data:** Junho de 2026

---

## 1. Objetivo

Adequar o modelo de avaliação em massa de imóveis do ITIV às normas técnicas
reconhecidas no Brasil, de forma que os valores estimados possam sustentar
lançamento tributário sem fragilidade técnica ou jurídica.

Normas de referência (lidas integralmente):

- **ABNT NBR 14653-1:2019** — Avaliação de bens, procedimentos gerais
- **ABNT NBR 14653-2:2011** — Imóveis urbanos
- **Norma IBAPE/SOBREA (2023)** — Avaliação em massa para fins tributários
- **IAAO** — Standard on Mass Appraisal (2017) + Standard on Ratio Studies (2013)

---

## 2. Princípio central (definido pelo usuário e confirmado pela norma)

> **A amostra de TREINO pode ter limites** (área, valor, etc.) para garantir
> qualidade do aprendizado.
> **A avaliação/INFERÊNCIA NÃO pode aplicar esses limites** — o modelo deve
> avaliar TODOS os imóveis do cadastro, sem exclusão.

**Fundamento normativo:**

- **IBAPE 7.6.7:** "Recomenda-se que os limites das variáveis relacionadas aos
  imóveis que integram a *amostra de dados* sejam compatíveis com as
  características do universo de imóveis a avaliar." → limite é da **amostra**.
- **IBAPE 7.9.1:** "As estimativas de valor serão resultantes da aplicação do(s)
  modelo(s) ao *universo de imóveis a ser avaliado*." → inferência cobre **todos**.

Imóveis atípicos (área muito fora do padrão, etc.) **não devem ser filtrados** na
inferência. Conforme **IBAPE 7.1.3(a)**, devem ser **sinalizados para avaliação
individual** — não excluídos nem distorcidos silenciosamente.

---

## 3. Análise de Lacunas — Modelo Atual × Norma

| # | Requisito da norma | Fonte | Modelo atual | Situação |
|---|---|---|---|---|
| 1 | Limites só na amostra de treino, nunca na inferência | IBAPE 7.6.7 / 7.9.1 | Limites de área/valor aplicados; inferência em lote pode herdá-los | **A corrigir** |
| 2 | Imóveis atípicos → avaliação individual sinalizada | IBAPE 7.1.3(a) | Não há sinalização; valores distorcidos passam | **A corrigir** |
| 3 | Validação por Nível Geral (mediana das razões) | IBAPE 7.8.1 | Usa MAPE/R²; não calcula Nível Geral | **Faltando** |
| 4 | Validação por COD (uniformidade horizontal) | IBAPE 7.8.1 / IAAO | Não calcula COD | **Faltando** |
| 5 | Uniformidade vertical (PRD/PRB) | IBAPE 7.8.1 / IAAO | Não calcula PRD/PRB | **Faltando** |
| 6 | Três amostras para ML (treino/val/teste) | IBAPE 7.8.4 | Possui split treino/val/teste | **Atende** |
| 7 | Critério de outlier fundamentado | NBR 14653-2 (Chauvenet) | Usa IQR×1,5 sem citar norma | **A documentar/revisar** |
| 8 | Coeficiente de segurança 70-90% | IBAPE 7.9.2 | Não aplica | **A avaliar** (é p/ IPTU; ITIV pode diferir) |
| 9 | Ciclo de reavaliação ≤ 4 anos | IBAPE 7.11.1 | N/A (modelo novo) | **Planejar** |
| 10 | Qualidade do cadastro (95% campos objetivos) | IAAO | Não medido | **Faltando** |
| 11 | ITBI: só transações 100% e representativas | IBAPE 7.2.11 | Verificar fração transmitida | **Verificar** |

---

## 4. Metas de desempenho (graus de fundamentação)

### Nível Geral das avaliações (mediana razão estimado/mercado)
| Grau | Faixa |
|---|---|
| III (máximo) | 0,90 a 1,10 |
| II | 0,70 a <0,90 |
| I | 0,50 a <0,70 |

### Uniformidade Horizontal — COD
| Grau (IBAPE) | Faixa |
|---|---|
| III | ≤ 15% |
| II | >15% e ≤30% |
| I | >30% e ≤50% |

### COD por tipo (IAAO Ratio Studies 2013)
| Tipo de imóvel | COD aceitável |
|---|---|
| Residencial (casa/apto) | 5 a 15 |
| Comercial (renda) | 5 a 20 |
| Terreno | 5 a 25 |

### Uniformidade Vertical (IAAO)
- **PRD:** 0,98 a 1,03
- **PRB:** −0,05 a +0,05 (inaceitável fora de −0,10 a +0,10)

---

## 5. Etapas do projeto

### Etapa 1 — Separar limites de treino × inferência
- Garantir que os limites (área, valor/m²) sejam aplicados **apenas** na
  construção da amostra de treino.
- Remover **qualquer** filtro de limite do pipeline de inferência/lote.
- Imóveis fora dos limites de treino: avaliar mesmo assim e **marcar** como
  "atípico — sujeito a avaliação individual" (IBAPE 7.1.3a).

### Etapa 2 — Implementar métricas normativas de validação
- Calcular, sobre a amostra de controle (transações reais do teste):
  - Nível Geral (mediana das razões estimado/preço)
  - COD (coeficiente de dispersão)
  - PRD e PRB
- Enquadrar o resultado nos graus de fundamentação (Tabela 1 IBAPE).

### Etapa 3 — Comparar modelo atual × modelo conforme norma
- Rodar as mesmas métricas no modelo atual e no ajustado.
- Quantificar a diferença: quantos imóveis mudam de classificação ao remover
  os limites de inferência.

### Etapa 4 — Documentação e fundamentação
- Documentar a origem de cada critério (ou substituir IQR por Chauvenet, se a
  equipe aprovar).
- Produzir memorial descritivo conforme IBAPE Seção 10.

### Etapa 5 — Decisões pendentes de aprovação da equipe
- Critério de outlier: manter IQR ou adotar Chauvenet (NBR 14653-2)?
- Coeficiente de segurança: aplicar ao ITIV? Qual percentual?
- Limites da amostra de treino: revisar com base no universo real do cadastro.

---

## 5-A. Decisões registradas com a equipe (seguir a norma)

| Tema | Decisão | Fundamento |
|---|---|---|
| Situação da transmissão | Incluir Baixado + Liberado + Em aberto | Decisão do auditor |
| Tipo de transação | Só "Compra e Venda" e "Compra e venda de garagem" | IBAPE 7.2.11 |
| Impugnação VVA | Excluir | Não é preço de livre mercado |
| Datas inválidas | Recuperar por registro/lavratura/assinatura; descartar só sem nenhuma | — |
| Fração transmitida | Só 100% | IBAPE 7.2.11(b) |
| **Divisão treino/teste** | **Aleatória 80/10/10 (treino/val/teste)** | **IBAPE 7.6.4 e 7.8.4** |
| **Contemporaneidade** | **Reportar honestamente — Grau II (16,8%)** | **IBAPE Tabela 1, item 5** |
| Segmentos pequenos | Agrupar em grupo maior | IBAPE 7.6.2 |

Base limpa resultante: **121.932 transações** (`base_limpa_normas.parquet`), período 2021–2026 (com poucos registros recuperados de 2017–2020).

## 6. Próximo passo imediato

Implementar a **Etapa 2** (métricas normativas) sobre os resultados que já
existem, para **medir objetivamente** onde o modelo atual está em relação às
metas da norma — antes de qualquer alteração no pipeline.

Nenhum limite, filtro ou critério novo será alterado sem apresentação e
aprovação prévia da equipe.
