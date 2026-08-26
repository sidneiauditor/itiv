# Fundamentação Normativa — Avaliação em Massa de Imóveis para o ITIV

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**
**Junho de 2026**

Este documento reúne as normas técnicas que fundamentam cada decisão metodológica
do projeto de avaliação em massa dos imóveis de Salvador, com citação direta dos
dispositivos aplicados.

---

## 1. Normas de referência

| Norma | Conteúdo |
|---|---|
| **ABNT NBR 14653-1:2019** | Avaliação de bens — Procedimentos gerais |
| **ABNT NBR 14653-2:2011** | Avaliação de bens — Imóveis urbanos |
| **IBAPE/SOBREA (2023)** | Avaliação em massa para fins tributários e de políticas urbanas |
| **IAAO (2017)** | Standard on Mass Appraisal of Real Property |
| **IAAO (2013)** | Standard on Ratio Studies |

> A norma IBAPE/SOBREA detalha, para fins tributários, os procedimentos gerais da
> ABNT NBR 14653-1 (IBAPE, item 1 — Escopo).

---

## 2. Seleção dos dados de mercado

### 2.1 Quais transações usar (base do ITIV)
> **IBAPE 7.2.10:** "Recomenda-se que a base de dados do ITBI seja uma das fontes
> de dados de preços de venda, com a utilização exclusiva de dados sobre transações
> nas quais os preços declarados pelos contribuintes sejam representativos do valor
> de mercado."

> **IBAPE 7.2.11:** critérios de seleção:
> (a) incluir transações com financiamento;
> (b) **incluir apenas casos nos quais o percentual transmitido é igual a 100%**;
> (c) **não incluir** arrematação em hasta pública, desapropriação quando não
> reflitam condições normais de compra e venda.

**Aplicação no projeto:**
- Mantidas só "Compra e Venda" e "Compra e venda de garagem"
- Excluídas: arrematação, permuta, dação, adjudicação, fiduciária, incorporação,
  isenção/imunidade e resultados de impugnação do VVA
- Mantidas só transmissões de 100% da fração
- Resultado: 121.932 transações (de 148.811 brutas)

### 2.2 Verificação de confiabilidade
> **IBAPE 7.2.14:** "Recomenda-se que os dados sejam verificados, de forma a garantir
> sua confiabilidade em relação ao preço e data do evento."

**Aplicação:** datas inválidas recuperadas por registro/lavratura/assinatura;
descartadas só as sem nenhuma data válida (61 linhas).

---

## 3. Tratamento e consistência dos dados

### 3.1 Análise exploratória e saneamento
> **IBAPE 7.6.6:** "Recomenda-se que as análises exploratórias preliminares abranjam,
> além das técnicas estatísticas clássicas, as de natureza espacial (...) para
> identificar casos atípicos (outliers espaciais) (...) ou sanar erros oriundos da
> etapa de coleta e armazenamento dos dados."

> **NBR 14653-2:2011 (item B.3 — Saneamento da amostra), texto literal:** "Após a
> homogeneização, devem ser utilizados critérios estatísticos consagrados de eliminação
> de dados discrepantes, para o saneamento da amostra. Os dados discrepantes devem ser
> retirados um a um, com início pelo que esteja mais distante da média. Admite-se a
> reintrodução de dados (...)."

**Observação importante:** a NBR 14653-2 **não nomeia** o critério de Chauvenet (nem
nenhum outro específico) — exige apenas "critérios estatísticos consagrados" e o
procedimento **iterativo** (um a um, do mais distante da média). O critério de Chauvenet
é uma escolha **compatível** com essa exigência, mas não é "recomendado pela norma" no
sentido literal.

**Aplicação no projeto:** validação de consistência (incompletos, incompatíveis,
duplicidades) executada **sem exclusão** — Etapa 2. Tratamento de outliers comparou
Z-Score, IQR, Mahalanobis e Chauvenet; recomendação técnica por Chauvenet, a ser
aplicado de forma **iterativa** conforme o procedimento da NBR 14653-2 B.3, **somente
na amostra de treino**.

### 3.2 Limites das variáveis — princípio central
> **IBAPE 7.6.7:** "Recomenda-se que os limites das variáveis relacionadas aos imóveis
> que integram a **amostra de dados** sejam compatíveis com as características do
> universo de imóveis a avaliar."

> **IBAPE 7.9.1:** "As estimativas de valor serão resultantes da aplicação do(s)
> modelo(s) de avaliação desenvolvido(s) ao **universo de imóveis a ser avaliado**."

**Interpretação aplicada:** limites (área, valor) valem **somente** para a amostra de
TREINO. Na **inferência**, o modelo avalia **todos** os imóveis, sem filtro. Imóveis
atípicos são **sinalizados** para avaliação individual (ver 4.2), nunca excluídos.

---

## 4. Modelagem

### 4.1 Método e segmentação
> **IBAPE 7.3.1:** "Para a identificação do valor de mercado, sempre que possível
> preferir o método comparativo direto de dados de mercado."

> **IBAPE 7.3.2:** "Recomenda-se o desenvolvimento de modelos específicos para cada
> segmento imobiliário."

> **IBAPE 7.6.2:** admite amostra única com variável que identifique o segmento
> quando não há dados suficientes por segmento.

**Aplicação:** modelos por grupo (Apartamento, Casa, Comercial, Terreno); segmentos
pequenos (Box, Galpão, etc.) agrupados.

### 4.2 Imóveis atípicos
> **IBAPE 7.1.3(a):** "Recomenda-se o uso de avaliações individuais para avaliar
> imóveis atípicos, cujo valor não possa ser estimado com grau aceitável de acurácia
> por intermédio de modelos genéricos (shopping centers, hospitais, aeroportos,
> imóveis históricos, etc.)."

**Aplicação:** imóveis fora do padrão da amostra de treino recebem o valor estimado
**e** uma marcação de "atípico — sujeito a avaliação individual".

### 4.3 Métodos não paramétricos (Machine Learning)
> **IBAPE 8.1.2:** "Quando forem utilizadas outras ferramentas analíticas (...) técnicas
> de aprendizado de máquina e redes neurais artificiais, podem ser aplicadas, desde
> que devidamente justificadas do ponto de vista teórico e prático, com a inclusão de
> validação."

> **IBAPE 7.8.4:** para métodos não paramétricos, "recomenda-se a divisão dos dados em
> **três amostras**" (treino, validação e teste).

**Aplicação:** LightGBM + modelo hedônico + KNN, com três amostras.

### 4.4 Significância dos parâmetros e amostra mínima (NBR 14653-2, verificado no texto oficial)

> **Nível de significância máximo para rejeição da hipótese nula de cada regressor
> (teste bicaudal):** Grau III = **10%** · Grau II = **20%** · Grau I = **30%**.

> **Nível de significância máximo do modelo (global):** Grau III = **1%** · Grau II = **2%**
> · Grau I = **5%**.

> **Amostra mínima** em função do número de variáveis independentes (k):
> n ≥ 3(k+1) para n ≤ 30; n ≥ 3k para 30 < n ≤ 100; n ≥ 10% n_i para n > 100.

**Observação:** estes critérios são da modelagem por **regressão**. Para modelos de
Machine Learning, a IBAPE 8.1.2.1 dispensa a especificação formal — porém os testes de
significância são usados no projeto como **diagnóstico** da contribuição de cada
parâmetro (Etapa 5). A amostra de apartamentos (97.990) supera com folga o mínimo.

---

## 5. Divisão da amostra

> **IBAPE 7.6.3:** divisão em amostra de construção e amostra de controle (hold-out).

> **IBAPE 7.6.4:** "particão aleatória dos dados (...) em uma das seguintes proporções:
> 90%-10%; 85%-15% ou 80%-20%."

**Aplicação:** sorteio aleatório, semente fixa = 42 (reproduzível), proporção
80% treino / 10% validação / 10% teste.

---

## 6. Validação do modelo

### 6.1 Indicadores obrigatórios
> **IBAPE 7.8.1:** "Devem ser calculados indicadores de desempenho para a amostra de
> controle relacionados ao **nível geral** e à **uniformidade das avaliações**."
> - Nível geral = mediana dos níveis individuais (razão estimado/preço)
> - Uniformidade horizontal = **coeficiente de dispersão (COD)** [passo a passo em 7.8.1.b]
> - Uniformidade vertical = regressividade/progressividade

### 6.2 Metas (graus de fundamentação — IBAPE Tabela 1)
| Item | Grau III | Grau II | Grau I |
|---|---|---|---|
| Nível geral | 0,90 a 1,10 | 0,70 a <0,90 | 0,50 a <0,70 |
| Uniformidade horizontal (COD) | ≤ 15% | >15% e ≤30% | >30% e ≤50% |
| Contemporaneidade (últimos 12 m) | ≥ 20% | ≥ 10% | demais |

### 6.3 Padrões internacionais complementares (IAAO Ratio Studies 2013)
- **COD aceitável:** residencial 5–15; comercial 5–20; terreno 5–25
- **PRD (uniformidade vertical):** 0,98 a 1,03
- **PRB:** −0,05 a +0,05 (inaceitável fora de −0,10 a +0,10)

---

## 7. Aplicação e manutenção

### 7.1 Coeficiente de segurança
> **IBAPE 7.9.2:** "Para fins de lançamento do IPTU, recomenda-se a aplicação de um
> coeficiente de segurança único, compreendido entre **70% e 90%** sobre os valores
> estimados, de forma a minimizar casos de superavaliação."

*Observação: previsto para IPTU; aplicação ao ITIV é decisão da equipe.*

### 7.2 Ciclo de reavaliação
> **IBAPE 7.11.1:** "Recomenda-se que o ciclo entre avaliações genéricas seja de, no
> máximo, **4 (quatro) anos**."

> **IBAPE 7.12.1:** monitoramento anual do desempenho das avaliações.

---

## 8. Transparência

> **IBAPE 9.2.2:** apresentação dos resultados em audiências públicas.

> **IBAPE 9.2.3:** "recomenda-se livre acesso aos resultados dos trabalhos para
> qualquer imóvel cadastrado, por qualquer cidadão."

> **IBAPE 7.1.2(a):** o processo de avaliação deve ser "essencialmente técnico e
> transparente."

---

*Todas as citações foram extraídas da leitura integral dos documentos normativos.
As decisões metodológicas do projeto estão registradas em
`REGISTRO_ETAPAS_APROVACAO.md`, sujeitas à aprovação da equipe.*
