# Lista Final de Parâmetros — Modelo de Apartamentos (ITIV)

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**
**Documento para aprovação da equipe — fecha a fase de Engenharia de Parâmetros**

Destinatários da avaliação: SEFAZ, contribuintes e Procuradoria do Município de Salvador.

---

## 1. Objetivo deste documento

Apresentar, para aprovação, a lista definitiva de parâmetros (características do imóvel)
que o modelo de avaliação de **apartamentos** usará para estimar o valor de mercado.
Cada decisão é fundamentada nas Etapas 1 a 7 da engenharia de parâmetros e nas normas
ABNT NBR 14653-1/2, IBAPE/SOBREA 2023 e IAAO.

---

## 2. Parâmetros que ENTRAM no modelo

| Parâmetro | Forma | Por que entra |
|---|---|---|
| **Área privativa** | log (ln) | É o parâmetro que mais explica o preço (Spearman 0,79). Representa as áreas (as outras são redundantes). 99,94% preenchido. |
| **Nº de pavimentos do prédio** | escala original | Estatisticamente significativo (p ≤ 10%, Grau III) e não redundante com a área. |
| **Localização** (setor fiscal + coordenadas) | categórica + espacial | Fator mais determinante do valor (até 13× entre setores; +0,088 de R²). Conforme IBAPE 7.7.3. |
| **Andar da unidade** | valor + marca "tem/não tem" | Influencia o preço, mas só 35% preenchido — entra com salvaguarda para os casos sem informação. |

---

## 3. Parâmetros que SAEM do modelo

| Parâmetro | Por que sai |
|---|---|
| **Área construída / construída da unidade** | Redundantes com a área privativa (correlação > 0,90; VIF > 10). Manter as três distorceria o modelo sem agregar informação. |
| **Fatores VLFC*** (construção, terreno, valor venal) | **Circularidade:** são derivados do valor venal atual da prefeitura — usá-los faria o modelo repetir o valor venal em vez de medir o mercado. Além disso, não agregam poder de previsão (R² +0,0002). |
| **Idade do imóvel** | Dado praticamente inexistente nesta extração (~0% preenchido). Recomenda-se solicitar ao cadastro para modelos futuros. |

---

## 4. Comprovações que sustentam estas decisões

- **Outliers:** remover 1,2% dos extremos eleva o poder de explicação de 50% para 70%
  (R²). Confirma o tratamento por critério estatístico consagrado (NBR 14653-2 B.3),
  a ser aplicado **só no treino** e de forma **iterativa**.
- **Transformação log:** comprovada — corrige a distorção dos extremos (a correlação
  área×preço sobe de ~0 para 0,57; a assimetria da área cai de 279 para 0,57).
- **Localização:** +0,088 de R² só com setor fiscal; mais ainda com coordenadas/KNN e
  com o modelo não-linear (LightGBM).

---

## 5. Salvaguardas mantidas

- Limites de área/valor (Chauvenet) valem **somente na amostra de treino**, nunca na
  inferência (IBAPE 7.6.7 / 7.9.1).
- O modelo avaliará **todos** os apartamentos do cadastro; atípicos são **sinalizados**
  para avaliação individual, nunca excluídos (IBAPE 7.1.3a).
- Qualquer proxy de localização será **causal** (sem vazamento do próprio imóvel).

---

## 6. Decisão da equipe

**Lista final de parâmetros:** ( ) Aprovada  ( ) Ajustar — _____________________

**Decisões pendentes que precisam sair junto (das etapas anteriores):**
1. Fatores VLFC*: ( ) Excluir (recomendado)  ( ) Manter — justificar
2. Método de outlier: ( ) Chauvenet iterativo (recomendado)  ( ) Outro
3. Andar da unidade com baixa cobertura: ( ) Entrar com flag (recomendado)  ( ) Excluir

Após a aprovação, segue-se para a **Etapa 4 — Treino do modelo de apartamentos**.
