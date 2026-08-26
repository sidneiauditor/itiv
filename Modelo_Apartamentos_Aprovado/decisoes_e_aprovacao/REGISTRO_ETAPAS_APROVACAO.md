# Registro de Etapas — Refazimento do Avaliador ITIV conforme Normas

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**
Cada etapa abaixo aguarda **aprovação da equipe** antes de prosseguir.

---

## Etapa 0 — Construção da base limpa  ✅ concluída

Critérios aplicados (fundamento: IBAPE 7.2.11):
- Situação: Baixado + Liberado + Em aberto (exclui Cancelado)
- Tipo: só "Compra e Venda" e "Compra e venda de garagem"
- Datas inválidas recuperadas por registro/lavratura/assinatura
- Só transmissões de 100%
- VLTRANSACAO > 0

**Resultado:** 121.932 transações (81,9% do bruto de 148.811).
Arquivo: `base_limpa_normas.parquet`

**Aprovação da equipe:** ( ) Aprovado  ( ) Ajustar — _____________

---

## Etapa 1 — Divisão treino/validação/teste  ⚠️ revisar antes de aprovar

Método: sorteio aleatório (IBAPE 7.6.4 e 7.8.4), proporção 80/10/10,
semente fixa = 42 (reproduzível).

| Arquivo | Linhas | % |
|---|---|---|
| treino.parquet | 97.545 | 80,0% |
| validacao.parquet | 12.193 | 10,0% |
| teste.parquet | 12.194 | 10,0% |

Proporções de tipologia equilibradas nos três conjuntos.

**⚠️ Pendência detectada:** 12 transações com `SQTRANSMISSAO` duplicado
(121.932 linhas × 121.920 IDs únicos). Precisa resolver as duplicatas
**antes** de finalizar a divisão.

**Aprovação da equipe:** ( ) Aprovado após corrigir duplicatas  ( ) Ajustar — ______

---

## Etapa 2 — Validação de consistência (NBR 14653)  ✅ medido — aguarda decisão

Fundamento: NBR 14653-2:2011 (análise de consistência da amostra) e
IBAPE 7.6.6 (sanar erros da coleta e armazenamento dos dados).
**Nenhuma linha foi excluída — apenas medição.**

### 2.1 Dados incompletos (% faltante)
| Campo | Faltante |
|---|---|
| Preço de venda, área terreno, setor fiscal, valor venal | 0,0% |
| Tipologia | 0,1% |
| Área privativa | 0,4% |
| Coordenadas X/Y | 2,3% |
| Pavimentos | 3,9% |

### 2.2 Valores incompatíveis (contagem, sem corte)
- Área privativa ≤ 0 ou nula: **625**
- R$/m²: mínimo 0 · p1 R$ 101 · **mediana R$ 4.176** · p99 R$ 14.817 · máximo R$ 19.972.849
- Há valores extremos (próximos de 0 e na casa dos milhões/m²) a investigar.

### 2.3 Duplicidades
- `SQTRANSMISSAO` repetido: **12** linhas
- Mesma inscrição + data + valor: **13.239 linhas** em 4.586 grupos

**⚠️ NÃO se concluiu a causa.** As duplicidades por inscrição+data+valor podem ser:
duplicata real, venda conjunta (imóvel + garagem na mesma inscrição), ou reentrada.
**Requer investigação da equipe antes de qualquer remoção.**

### Decisões necessárias da equipe
1. Os 12 `SQTRANSMISSAO` repetidos: remover (manter 1ª ocorrência)?
2. As 13.239 linhas inscrição+data+valor: investigar amostra antes de decidir?
3. Os 625 sem área privativa: usar área de terreno como alternativa?
4. Valores extremos de R$/m²: tratar na Etapa 3 (outliers) — sem corte agora.

**Aprovação da equipe:** ( ) Aprovado  ( ) Ajustar — _____________

---

### 2.4 Análise aprofundada das duplicidades (preparação p/ a equipe)

Classificação dos 4.586 grupos (mesma inscrição + data + valor):
- **4.586 grupos (100%)** são linhas **totalmente idênticas** em tipologia,
  subunidade e área. **Nenhum** difere em subunidade/tipologia → a hipótese de
  "venda conjunta" (imóvel + garagem) **não se sustenta nos dados**.
- Comprador e vendedor: **idênticos** em 100% dos grupos.
- Valor do ITIV: idêntico em todos menos 1.
- Porém a **data de solicitação** varia em 4.462 grupos e a **situação** em 1.952
  (ex.: uma linha "Baixado", outra "Em aberto").

**Fato, sem conclusão de causa:** mesmo imóvel, mesma venda, mesmas partes, mesmo
valor — com solicitações em datas/situações diferentes. A equipe decide o significado.

---

## Etapa 3 — Tratamento de outliers  ✅ medido — aguarda escolha da equipe

Comparação dos 4 métodos sobre o TREINO (97.545), em log(R$/m²) por tipologia.
**Nada foi excluído.** Aplicação futura: SOMENTE no treino (IBAPE 7.6.7 / 7.9.1).

| Método | Marcaria | % | Perfil |
|---|---|---|---|
| Chauvenet | 466 | 0,5% | Mais conservador |
| Z-Score (>3σ) | 836 | 0,9% | Conservador |
| Mahalanobis (χ², 99%) | 1.745 | 1,8% | Multivariado |
| IQR ×1,5 (modelo atual) | 4.573 | 4,7% | Mais agressivo |

461 transações são marcadas pelos 4 métodos (casos indiscutíveis).

Exemplos que o Chauvenet marca: apto 39 m² por R$ 778 mi (R$ 20 mi/m²);
casa por R$ 0,01; "Outros" 26.143 m² por R$ 1,00 → erros/valores simbólicos.

**Recomendação técnica:** Chauvenet — critério estatístico consagrado que **atende**
à exigência da NBR 14653-2 (item B.3: eliminação de discrepantes por critério
consagrado, um a um a partir do mais distante da média). É o mais cirúrgico
(0,5%, sem cortar vendas legítimas). **A NBR 14653-2 não nomeia Chauvenet** — exige
critério consagrado e aplicação **iterativa**; Chauvenet satisfaz ambos.

**Decisão da equipe:** ( ) Chauvenet  ( ) IQR  ( ) Z-Score  ( ) Mahalanobis  ( ) Combinar

---

## Etapa 6 (parcial) — Comparação modelo atual × valor venal  ✅ medido

Estudo de razões sobre 5.591 transações de teste (estimativa ÷ preço de venda real),
conforme IBAPE 7.8.1 e IAAO.

| Métrica | Valor Venal atual | Modelo Boost | Modelo Hedônico | Meta |
|---|---|---|---|---|
| Nível Geral | 0,867 (Grau II) | 0,975 (Grau III) | 0,995 (Grau III) | 0,90–1,10 |
| COD | 35,4% (fora) | 23,6% (Grau II) | 25,3% (Grau II) | ≤15% |
| PRD | 1,115 | 1,127 | 1,156 | 0,98–1,03 |
| PRB | −0,015 | −0,054 | −0,077 | −0,05/+0,05 |

**Leitura:** o modelo melhora o Nível Geral (II→III) e a uniformidade horizontal
(COD 35%→24%); a uniformidade vertical (PRD/PRB) ainda não atinge a meta — ponto a
tratar no refazimento.

*Observação: este resultado é do MODELO ATUAL (treinado na base antiga). Após o
refazimento conforme norma, esta comparação será refeita.*

---

## Decisões da equipe (registradas em 22/06/2026)

1. **Duplicidades inscrição+data+valor (13.239):** MANTER os dados na base.
   - *Recomendação técnica pendente de confirmação:* manter na base para auditoria,
     mas contar cada venda uma única vez no TREINO (evita peso extra da mesma venda).
2. **Escopo inicial do modelo:** somente **APARTAMENTOS** (97.990 transações).
   - Fundamento: segmento mais homogêneo e de maior massa (IBAPE 7.3.2).
   - Casas, terrenos e comerciais: modelos próprios em fase posterior.
   - 59 apartamentos sem área privativa: tratar (excluir do treino ou usar fração
     ideal) — área de terreno NÃO serve para apartamento.
3. **Coeficiente de segurança:** **A DEFINIR após medir o COD do modelo de
   apartamentos.** Proposta da equipe (95%) será reavaliada com o COD em mãos,
   para fundamentar eventual saída da faixa 70–90% da IBAPE 7.9.2.

---

## Etapa 3-A — Engenharia e avaliação de parâmetros  🔄 em andamento

Seleção e avaliação das variáveis (parâmetros) do modelo de apartamentos,
conforme IBAPE 7.7 e NBR 14653-2.
Documento dedicado: `Engenharia_Parametros_Apartamentos.docx` (incremental).

### Etapas 1 e 2 (levantamento + disponibilidade) — ✅ concluídas
97.990 apartamentos · 20 parâmetros levantados e medidos.

**Apontamentos da análise (atenção da equipe):**

1. **⚠️ Circularidade dos fatores VLFC* (crítico).** `VLFCCONSTRUCAO`,
   `VLFCTERRENO` e `VLFCVALORVENAL` têm 100% de preenchimento, MAS são os fatores
   que a prefeitura usa para calcular o valor venal atual. Usá-los como entrada do
   modelo faria a comparação "mercado × valor venal" ficar circular.
   **Recomendação: NÃO usar no modelo de mercado.** Decisão da equipe.

2. **Andar da unidade (NUPAVIMENTOUNIDADE): só 35% utilizável.** Usar apenas com
   marca de "tem/não tem andar"; não depender fortemente.

3. **Idade (DTINICIOCONSTRUCAO/DTALVARACONSTRUCAO): ~0%.** Dado inexistente nesta
   extração. Fica de fora; solicitar ao cadastro para modelos futuros.
   - **Verificado no CADASTRO COMPLETO (922.510 imóveis):** idade também ausente —
     data de alvará em só 803 imóveis (0,1%); apartamentos só 104 de 368.052 (0,0%).
     Confirma que a ausência é na origem do dado, não na extração de transações.
     Fontes alternativas a avaliar: base de Habite-se, alvarás de construção, IPTU.

**Parâmetros confiáveis (alta disponibilidade):** área privativa (99,94%),
setor fiscal (99,99%), coordenadas (98,4%), nº pavimentos do prédio (77%).

**Decisão da equipe sobre os VLFC*:** ( ) Excluir (recomendado)  ( ) Manter — justificar

### Etapa 3 (análise exploratória) — ✅ concluída

**Achado-chave — Pearson ≈ 0 vs Spearman alto:**
| Parâmetro | Pearson | Spearman |
|---|---|---|
| Área construída | 0,05 | 0,79 |
| Área privativa | 0,01 | 0,69 |
O Pearson baixo é **artefato dos outliers** (R$ 778 mi/apto, vendas de R$ 0,01),
não ausência de relação. O Spearman (0,79) mostra que **a área é o parâmetro que
mais explica o preço**. Confirma a necessidade do tratamento de outliers (Chauvenet)
e da transformação logarítmica.

**Localização (IBAPE 7.7.3):** setor mais caro R$ 16.590/m² × mais barato R$ 1.238/m²
= 13× de diferença. Localização é o parâmetro mais determinante.

**Outros:** VLFC* têm correlação ~0 com o preço (não ajudam, além da circularidade).
UTILIZACAOIMOVEL quase não varia (97.002 de 97.990 = "Residencial Vertical") →
pouco discriminante para apartamentos.

### Etapa 4 (transformações) — ✅ concluída

Transformação logarítmica comprovada (IBAPE 7.6.1d):
| Medida | Antes | Depois do log |
|---|---|---|
| Pearson área×valor | 0,011 | **0,566** |
| Skewness área | 279,1 | **0,57** |
| Skewness valor | 84,5 | −3,67 |

O log recupera a relação área×preço (Pearson 0→0,57) e normaliza a área (skew 279→0,57).
A assimetria residual do valor (−3,67) vem das vendas simbólicas (R$ 0,01 / R$ 1,00):
o log corrige os extremos altos; os baixos só saem com o **Chauvenet**. Confirma que
**log + Chauvenet se complementam** — a sequência definida está correta.

Transformações propostas: log para valor e área; escala original para contagens
(pavimentos, andar); localização tratada na Etapa 7.

### Etapa 5 (significância) — ✅ concluída

Regressão OLS (log valor ~ área + pavimentos), n=64.756, **Grau III global** (p≈0).
Cálculo por álgebra matricial (statsmodels indisponível) — matematicamente idêntico.

**1. Diagnóstico de outliers (prova definitiva):**
| | n | R² |
|---|---|---|
| Com todos | 64.756 | 0,50 |
| Sem 763 extremos (Chauvenet iterativo) | 64.460 | **0,70** |
Remover 1,2% dos dados eleva o R² de 50%→70%. Confirma o valor do tratamento de outliers.

**2. VLFC* inúteis (prova):** R² sem VLFC = 0,4996; com VLFC = 0,4998 (+0,0002 = nada).
Além da circularidade, não ajudam a prever o preço. **Excluir.**

**3. Significativos (p≤10%, Grau III):** LOG_AREA, NUPAVIMENTOS, VLAREACONSTR,
VLAREACONSTRUN. VLAREAFRACAOIDEAL não significativa.

**Nota:** R² de 50% é só com área/pavimentos — a localização (fator mais forte) entra
na Etapa 7 e eleva o R². n=64.756 (<97.990) por exigir preditores preenchidos.

### Etapa 6 (redundância) — ✅ concluída

As 3 colunas de área são redundantes entre si (correlação > 0,90):
| Par | Pearson |
|---|---|
| Construída × construída unidade | 0,94 |
| Privativa × construída | 0,93 |
| Privativa × construída unidade | 0,92 |
VIF alto: VLAREAUSOPRIV 14,6 · VLAREACONSTR 14,0 (>10 = multicolinearidade).

**Recomendação:** manter **VLAREAUSOPRIV** (área privativa) como representante das áreas
(99,94% preenchida, área de uso do morador); dispensar VLAREACONSTR e VLAREACONSTRUN.
NUPAVIMENTOS não é redundante com área — permanece.

### Resumo dos parâmetros até a Etapa 6
| Parâmetro | Situação |
|---|---|
| Área privativa | Entra (representante das áreas) |
| Área construída / construída unidade | Saem (redundantes) |
| Nº de pavimentos | Entra (significativo, não redundante) |
| Localização (setor/coordenadas) | Etapa 7 |
| Andar da unidade | Atenção — só 35% |
| Fatores VLFC* | Saem (circularidade + R² +0,0002) |
| Idade | Sem dado (~0%) |

### Etapa 7 (localização) — ✅ concluída

| Regressão | R² |
|---|---|
| Só área + pavimentos | 0,403 |
| + setor fiscal (106 setores) | 0,491 |
| **Ganho da localização** | **+0,088** |
Proxy de vizinhança KNN10: correlação 0,41 com o preço (viável e causal).

A localização agrega ~9 pontos de R² (confirma IBAPE 7.7.3). O ganho parece modesto
porque: (1) outliers ainda presentes deprimem o R²; (2) sobreposição com porte do
prédio; (3) setor categórico é grosseiro — coordenadas/KNN e o LightGBM extraem mais.
**Recomendação:** CDSETORFISCAL como base + coordenadas/KNN como alternativa, sempre
causal (sem vazamento).

---

## ✅ ENGENHARIA DE PARÂMETROS — CONCLUÍDA (Etapas 1 a 7)

### Lista final de parâmetros do modelo de apartamentos (para aprovação)
| Parâmetro | Decisão | Fundamento |
|---|---|---|
| Área privativa (log) | ENTRA | Spearman 0,79; representante das áreas (Etapas 3,5,6) |
| Nº de pavimentos | ENTRA | Significativo p≤10%, não redundante (Etapa 5) |
| Localização (setor + coordenadas) | ENTRA | +0,088 R²; fator mais forte (Etapa 7) |
| Andar da unidade (+ flag tem/não tem) | ENTRA com cautela | Só 35% preenchido (Etapa 2) |
| Área construída / construída unidade | SAI | Redundantes r>0,90, VIF>10 (Etapa 6) |
| Fatores VLFC* | SAI | Circularidade + R² +0,0002 (Etapas 1,5) |
| Idade (DTINICIO/DTALVARA) | SAI | Dado inexistente ~0% (Etapa 2) |

**Decisão da equipe sobre a lista final:** ( ) Aprovada  ( ) Ajustar — __________

### Etapa 4 (treino) — ⏳ liberada após aprovação da lista + decisões da Etapa 2/3

## Etapa 4 — Treino do modelo refeito (apartamentos)  ✅ concluída (14/07/2026)

Executada em 09/07/2026 e re-executada em 14/07/2026 com as duas decisões da
equipe de 14/07/2026:
- **Filtro de plausibilidade** (substitui o corte de vendas simbólicas):
  Compra e Venda exato + Apartamento + VLITIV > 0 + desvio venal × transação ≤ ±30%.
  Motivo: restabelecer a leitura de PRD/PRB. Base: 97.990 → 46.392 transações.
- **Nível de confiança de 90%** para a sinalização (D5): 1.596 sinalizados
  (17,2% do teste final).

GridSearch ampliado para 5 famílias de modelos (LightGBM venceu; ElasticNet,
RF, Extra Trees e HistGB documentados em metricas_cv_apartamentos.json).

**Resultado no holdout:** LightGBM razão 0,999 | COD 9,6% | PRD 1,017 |
PRB −0,0088 — **todas as metas IAAO atendidas**. Hedônico como âncora (D6).
Relatório: `Relatorio_Etapa4_Treino_Modelo_Apartamentos_20260714.docx`

**Aprovação da equipe (D4 — aprovação formal do modelo):** (X) Aprovado em 14/07/2026

## Etapa 5 — Validação normativa completa  ✅ executada e aprovada (14/07/2026)

Relatório: `Relatorio_Etapa5_Validacao_Normativa_20260714.docx`
Scripts: `etapa5_validacao_normativa.py` (+ gráficos e relatório).

**Enquadramento:** hedônico com **Grau II de fundamentação** (15 pontos,
NBR 14653-2 Tabelas 1/2, com item 5 fundamentado pela análise da variância
por partes, A.3.2) e **Grau III de precisão** (amplitude mediana do IC 80% =
2,05%). LightGBM validado conforme IBAPE/SOBREA 2023 (8.1.2 — ML não é
objeto de especificação; exige justificativa + validação, ambas documentadas).

**Razões por segmento (IAAO, teste final):** razão mediana dentro de
0,90–1,10 nos 10 decis de valor e nos 70 setores com n≥10; COD ≤ 15% em
todos os decis e em 63/70 setores.

**Comparação com o valor venal atual (com ressalva metodológica do filtro
±30%):** venal razão 0,851 (subavaliação) vs LightGBM 0,999.

### Decisões da equipe (Etapa 5) — resolvidas em 14/07/2026
1. **Agrupamento de setores:** aplicado 177→175 e 179→162 (critério: distância
   ≤ 1km E diferença de preço/m² ≤ 20% vs. vizinho com n≥10). Os demais 14
   setores com poucos dados não atenderam ao critério (preço muito diferente
   do vizinho mais próximo — divisa entre bairros distintos) e permanecem
   sem agrupamento forçado. Hedônico mantido em Grau II (item 5 sustentado
   pela análise da variância por partes).
2. **Pontos com Cook > 1:** eram 4, todas transações em setores com 1 único
   dado no treino (causa estatística, não erro de dado — decisão da equipe:
   não remover). O agrupamento 177→175 já resolveu 1 caso; restam 3
   (setores 122, 166, 172, ainda isolados).
3. **Pendente:** administração informar itens 1–3 da Tabela 1 IBAPE
   (cadastro/OMI) — não depende do modelo; item institucional, não bloqueia
   a aprovação do modelo.

**Aprovação da equipe:** (X) Aprovado em 14/07/2026

---

## Etapa 6 — Promoção idade + inscrição relativa  ✅ 26/08/2026

**Candidato:** `idade_mais_rel` (pacote `Modelo_Apartamentos_Candidato_Idade_20260811`).

**Motivação:** achado do Relatório 114/2026 / David Taira — concentração de
“Compatível” em imóveis novos (inscrição > 900.000); estoque antigo com
aderência inferior. Testes da CIF confirmaram ganho nos antigos sem prejuízo
aos novos.

**Autorização formal:** e-mail David Yukishigue Taira → Marcos José de Souza Costa,
25/08/2026 — concordância com inclusão de depreciação/idade; sem novas sugestões;
encerramento da revisão do Relatório 114/2026.

**Holdout (candidato promovido):** COD mediano 6,383% · COD 9,231% · PRD 1,0157 · PRB −0,0084.

**Produção atualizada:**
- `Modelo_Apartamentos_Aprovado/dados/modelo_lightgbm_apartamentos.txt`
- legado 14/07/2026 em `dados/legado_v20260714/`
- avaliador HTML (`app/avaliador_web_apartamentos.py`) passa a usar idade +
  inscrição relativa no setor
- registro: `dados/registro_promocao_idade_rel.json`

**Aprovação da equipe:** (X) Promovido em 26/08/2026
