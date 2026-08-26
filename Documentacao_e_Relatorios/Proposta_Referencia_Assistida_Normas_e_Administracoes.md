# Proposta — Referência Assistida por Tipologia no ITIV
## Fundamentação normativa e práticas de outras administrações

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**  
**Data:** 20/07/2026  
**Status:** proposta para alinhamento interno (equipe + Dilson) e apresentação à direção  
**Complementa:** modelo de apartamentos aprovado em 14/07/2026; `ESPECIFICACAO_REGIMES_POR_TIPOLOGIA.md`; `FUNDAMENTACAO_NORMATIVA.md`

---

## 1. Objetivo

Formalizar, com base nas normas técnicas de avaliação em massa, um **regime de referência assistida** para tipologias de imóvel que **ainda não possuem modelo de mercado validado** (casa, loja, sala, terreno e segmentos menores), e para **apartamentos atípicos / de alto valor** fora do envelope confiável da amostra.

A proposta responde à exigência de haver **especificação para todos os tipos de imóvel**, ainda que, em parte deles, a linha adotada seja a da **PGV / valor venal cadastral**, com decisão humana — e não um modelo de machine learning forçado sobre amostra insuficiente.

---

## 2. Contexto do problema

| Situação | Evidência no projeto |
|----------|----------------------|
| Modelo ML validado só para apartamentos | Etapas 4 e 5 aprovadas em 14/07/2026; metas IAAO atendidas |
| Apartamentos ≈ 80% da base limpa | 97.990 de 121.932 transações |
| Casa, loja, terreno com massa limitada após filtros | Casa ~3.050; Loja ~734; Terreno ~292 (VLITIV>0 e desvio venal ≤±30%) |
| Avaliador novo recusa tipologias sem modelo | Comportamento atual: mensagem de erro se não for Apartamento |
| Direção exige especificação para todos os tipos | Alinhamento de 20/07/2026 — “ainda que seja adotar a linha da PGV” |

**Decisão já registrada (22/06/2026):** escopo inicial só apartamentos; demais tipologias em fase posterior. Esta proposta **não anula** essa decisão: ela **preenche a lacuna operacional** até existir modelo próprio por segmento.

---

## 3. O que é a referência assistida

### 3.1 Definição

**Referência assistida** é o regime em que o sistema:

1. identifica a tipologia e o enquadramento (típico / atípico);
2. apresenta o **valor venal cadastral** decorrente da **PGV** (e dados cadastrais associados);
3. informa, de forma explícita, que **não se trata** da estimativa de mercado do modelo validado;
4. **não autua automaticamente** com o mesmo limiar de confiança do modelo de apartamentos;
5. registra o regime usado;
6. deixa a **decisão** (aceitar, diligenciar, arbitrar ou encaminhar laudo) ao **avaliador humano**.

### 3.2 O que a PGV é (e o que não é)

| PGV / valor venal | Modelo de mercado (apartamentos) |
|-------------------|----------------------------------|
| Instrumento cadastral da Prefeitura (planta de valores + fatores) | Inferência estatística / ML sobre transações de compra e venda |
| Base típica do **IPTU** | Estimativa de **valor de mercado** para apoio ao ITIV |
| Disponível para **todos** os imóveis cadastrados | Validado só onde há amostra e estudo de razões |
| Nos testes do projeto, venal ~15% abaixo do mercado (aptos) | Razão mediana ~0,999; COD 9,6% (teste final) |

**PGV (Planta Genérica de Valores):** define valores unitários de referência (em geral R$/m² de terreno e de construção por zona/setor), que, combinados a áreas e fatores cadastrais (padrão, uso, correções), geram o **valor venal** do imóvel.

Nos dados do ITIV, o produto prático da PGV aparece principalmente como:

- `VLVENALCADASTRO` — valor venal no cadastro (~100% preenchido na base limpa);
- `VLVENALCORRIGIDO` — venal corrigido (~97%);
- fatores `VLFCTERRENO`, `VLFCCONSTRUCAO`, `VLFCVALORVENAL`;
- localização via `CDSETORFISCAL` e áreas do cadastro.

### 3.3 Três regimes operacionais

| Código | Nome | Uso |
|--------|------|-----|
| `MERCADO_ML` | Estimativa de mercado (modelo) | Apartamento na faixa validada |
| `PGV_ASSISTIDO` | Referência assistida (PGV/venal) | Casa, loja, sala e demais com venal utilizável, sem modelo de mercado |
| `AVALIACAO_INDIVIDUAL` | Avaliação individual | Terreno, tipologias raras, atípicos, aptos fora do envelope |

### 3.4 Matriz por tipologia (proposta)

| Tipologia | Regime V1 | Fonte | Sinalização automática ITIV? |
|-----------|-----------|-------|------------------------------|
| Apartamento (faixa da amostra) | `MERCADO_ML` | LightGBM + hedônico âncora | Sim (confiança 90%) |
| Apartamento atípico / alto valor | `AVALIACAO_INDIVIDUAL` | Estimativa ML com **alerta** + PGV de apoio | Não pelo ponto central isolado |
| Casa | `PGV_ASSISTIDO` | Venal/PGV | Não — auditor decide |
| Loja / Sala / Sobre-loja | `PGV_ASSISTIDO` | Venal/PGV | Não — auditor decide |
| Terreno | `AVALIACAO_INDIVIDUAL` | Venal ou laudo | Não |
| Garagem, box, galpão, outros | `AVALIACAO_INDIVIDUAL` | Laudo / análise | Não |

### 3.5 Fluxo na tela / no processo

Para regime `PGV_ASSISTIDO`, o sistema deve exibir no mínimo:

1. tipología e inscrição;
2. valor venal cadastral;
3. áreas e setor fiscal;
4. valor declarado na transmissão (quando houver);
5. diferença percentual declarado × venal (informativa);
6. texto fixo de enquadramento normativo (seção 5.4);
7. campos de decisão do auditor e código do regime no log/export.

---

## 4. Fundamentação nas normas técnicas

Normas de referência do projeto (já adotadas em `FUNDAMENTACAO_NORMATIVA.md`):

- ABNT NBR 14653-1:2019 — Avaliação de bens — procedimentos gerais  
- ABNT NBR 14653-2:2011 — Imóveis urbanos  
- IBAPE/SOBREA (2023) — Avaliação em massa para fins tributários  
- IAAO (2017) — *Standard on Mass Appraisal of Real Property*  
- IAAO (2013) — *Standard on Ratio Studies*

### 4.1 Preferência pelo mercado — e limite da amostra

> **IBAPE 7.3.1:** para identificação do valor de mercado, sempre que possível preferir o **método comparativo direto de dados de mercado**.

> **IBAPE 7.3.2:** recomenda-se o desenvolvimento de **modelos específicos para cada segmento** imobiliário.

> **IBAPE 7.6.2:** admite-se amostra única com variável que identifique o segmento quando **não há dados suficientes** por segmento.

**Leitura aplicada:** o projeto priorizou apartamentos (segmento homogêneo e de maior massa). Para casa/loja/terreno, **não há ainda** modelo específico validado com as mesmas metas. A referência assistida é o regime **provisório e declarado** até essa validação existir — não um atalho que finja equivalência ao modelo de apartamentos.

### 4.2 Quando o modelo genérico não tem acurácia aceitável

> **IBAPE 7.1.3(a):** recomenda-se o uso de **avaliações individuais** para imóveis atípicos cujo valor não possa ser estimado com grau aceitável de acurácia por modelos genéricos.

**Leitura aplicada:** terreno, tipologias raras e apartamentos fora do envelope da amostra enquadram-se nesse dispositivo. A referência assistida (PGV + auditor) é o **elo operacional** entre “sem modelo ML” e “avaliação individual / decisão humana”, sem exclusão silenciosa do imóvel.

### 4.3 Universo coberto; atípicos sinalizados — nunca “apagados”

> **IBAPE 7.6.7:** limites das variáveis da **amostra** devem ser compatíveis com o universo a avaliar.  
> **IBAPE 7.9.1:** as estimativas resultam da aplicação do(s) modelo(s) ao **universo** de imóveis.

**Leitura aplicada (já princípio do projeto):** o treino pode filtrar; a inferência não some com o caso. Tipologias sem modelo ML **continuam no fluxo**, com regime explícito (`PGV_ASSISTIDO` ou `AVALIACAO_INDIVIDUAL`).

### 4.4 Machine learning só com justificativa e validação

> **IBAPE 8.1.2:** técnicas de aprendizado de máquina podem ser aplicadas **desde que devidamente justificadas**, com validação.

**Leitura aplicada:** forçar LightGBM (ou hedônico) em tipologias sem validação de razões (nível geral, COD, PRD/PRB) **viola** o padrão que o próprio projeto exigiu nas Etapas 4–5. A referência assistida **evita** essa fragilidade.

### 4.5 Metas de qualidade por tipo (IAAO)

O *Standard on Ratio Studies* (IAAO, 2013), já citado no projeto, admite faixas de COD distintas por tipo, por exemplo:

| Tipo | COD aceitável (referência IAAO) |
|------|----------------------------------|
| Residencial | 5 a 15 |
| Comercial | 5 a 20 |
| Terreno | 5 a 25 |

**Leitura aplicada:** mesmo com amostra maior no futuro, casa/comercial/terreno devem ser aprovados **com as metas do tipo**, não com a narrativa do COD 9,6% dos apartamentos.

### 4.6 IAAO — abordagem diferente quando faltam vendas

O *Standard on Mass Appraisal* (IAAO, 2017) estabelece, em síntese, que:

- o **comparativo de vendas** é preferível quando há vendas suficientes;
- para **comercial/industrial**, se faltam vendas e dados de renda, aplica-se a abordagem de **custo**, checando com as vendas disponíveis;
- para **terreno**, na ausência de vendas adequadas, admitem-se técnicas alternativas (alocação, abstração, uso antecipado, capitalização de renda do solo, residual, etc.).

**Leitura aplicada:** administrações maduras **não inventam modelo de vendas** onde não há massa. Usam outro método (custo / cadastro / individual) — o mesmo espírito desta proposta, adaptado ao ITIV via PGV/venal + auditor.

### 4.7 O que a referência assistida **não** pretende ser

A NBR 14653-2 e a IBAPE regulam a **fundamentação e precisão** de avaliações de mercado (graus). A PGV **não** recebe, nesta proposta, o enquadramento de Grau II/III de mercado obtido pelo hedônico/LightGBM nas Etapas 4–5.

Portanto:

- **não** se afirma que o venal “substitui” o modelo de mercado;  
- **não** se usa a PGV como base automática unilateral de ITIV à revelia do processo adequado;  
- **sim** se usa a PGV como **referência cadastral de apoio** à análise assistida, com transparência.

### 4.8 Ressalva jurídico-tributária (ITBI / ITIV × valor venal do IPTU)

O STJ, no **Tema 1113**, fixou que a base de cálculo do ITBI é o valor do imóvel em **condições normais de mercado**; o valor declarado presume-se condizente com o mercado e só pode ser afastado mediante **processo administrativo** adequado — não por valor de referência unilateral desvinculado desse procedimento.

**Implicação para esta proposta:** a referência assistida pela PGV é ferramenta de **inteligência e apoio à análise** no fluxo do ITIV, com decisão documentada do avaliador. **Não** se confunde com lançamento automático do imposto “pelo venal do IPTU” sem o devido processo. Essa distinção fortalece — e não enfraquece — a defesa normativa.

### 4.9 Texto padrão de enquadramento (para tela e dossiê)

> Para tipologias sem modelo de avaliação em massa de mercado validado para o segmento (IBAPE 7.3.2), e/ou quando o valor não possa ser estimado com grau aceitável de acurácia por modelo genérico (IBAPE 7.1.3(a)), o sistema disponibiliza o valor venal decorrente da Planta Genérica de Valores (PGV) como **referência cadastral assistida**. A análise da transmissão é **assistida**: a decisão sobre aceitação, diligência, arbitramento ou encaminhamento a avaliação individual cabe ao avaliador. Este regime **não** equivale à estimativa de mercado do modelo de apartamentos aprovado em 14/07/2026 (NBR 14653-2 / IBAPE 8.1.2 / estudo de razões IAAO).

---

## 5. Existem modelos semelhantes em outras administrações?

**Sim.** A lógica “método conforme a tipología e a disponibilidade de dados” é padrão em avaliação em massa — no Brasil e no exterior. O que varia é a ferramenta (PGV, custo, renda, ML, laudo), não o princípio.

### 5.1 Brasil — PGV como regra geral do IPTU; mercado como evolução

Estudo comparado (IPEA / literatura de Curitiba, São Paulo, Belo Horizonte e Rio de Janeiro) mostra que a maior parte das legislações municipais de avaliação para fins de **IPTU** adota o **método evolutivo** (valor do terreno + custo de reedição da edificação com fatores), operacionalizado via **planta / valores unitários** — ou seja, a família da **PGV** — ainda que a NBR privilegie o comparativo de mercado.

Consequências práticas observadas na literatura:

- a PGV (ou equivalente) é o **instrumento universal** de cobertura do cadastro;
- a atualização por **dados de mercado / inferência / ML** aparece como **evolução** ou recalibração da planta, não como abandono da cobertura cadastral;
- a **desatualização da PGV** prejudica a arrecadação e a equidade também no ITBI (ex.: estudos de caso municipais, como Porto Velho), o que reforça usar o venal com **cautela** e com auditor — nunca como “verdade de mercado” automática.

### 5.2 Brasil — modelagem híbrida (estatística + ML) para equidade da PGV

Há experiências acadêmicas e técnicas de **PGV equitativa / modelagem híbrida** (geoestatística, aprendizado de máquina e métodos clássicos) para **atualizar** plantas de valores com mais equidade. Isso confirma duas coisas úteis ao ITIV:

1. outras administrações e estudos **já misturam** cadastro (PGV) e modelos avançados;  
2. o híbrido costuma ser **faseado**: primeiro cobertura e governança; depois refinamento por segmento com dados.

A proposta de Salvador (ML validado em apartamentos + PGV assistida no restante) é coerente com essa trajetória.

### 5.3 IAAO / administrações anglo-saxãs — método por classe de imóvel

Pelo *Standard on Mass Appraisal* (IAAO):

| Situação | Prática recomendada |
|----------|---------------------|
| Residencial com muitas vendas | Comparativo de vendas / modelos de mercado |
| Comercial com renda disponível | Abordagem de renda |
| Comercial sem vendas/renda suficientes | **Abordagem de custo**, checada com vendas |
| Terreno sem vendas adequadas | Técnicas alternativas (não forçar comparativo vazio) |
| Imóveis únicos / não típicos | Avaliação individual / tratamento especial |

Isso é estruturalmente o mesmo desenho desta proposta: **não um único motor para tudo**.

### 5.4 O que Salvador já tinha na versão anterior do avaliador

O pacote `entrega_equipe_20260615` já documentava escopo em camadas:

- **Apartamento** — avaliação automática;  
- **Casa / Comercial** — assistido (modelo sugere com intervalo; auditor decide);  
- **Terreno / Garagem / Outros** — fora do automático → laudo/análise.

A proposta atual **recupera e formaliza** essa lógica, alinhando-a ao modelo novo (só apartamentos com validação normativa completa) e à exigência de especificação escrita para 100% das tipologias.

### 5.5 Síntese comparativa

| Administração / padrão | O que faz quando falta modelo de vendas do segmento |
|------------------------|-----------------------------------------------------|
| Municípios BR (IPTU clássico) | PGV / método evolutivo para o universo cadastral |
| Estudos de PGV híbrida | Recalibrar planta com mercado + ML, por etapas |
| IAAO | Trocar de abordagem (custo, renda, técnicas de terreno) ou individual |
| Salvador — esta proposta | `MERCADO_ML` onde validado; `PGV_ASSISTIDO` / individual no restante |

---

## 6. Critérios para sair da referência assistida (Fase 2)

Uma tipologia só deixa o regime `PGV_ASSISTIDO` / individual e ganha `MERCADO_ML` próprio se:

1. amostra de treino/teste suficiente após saneamento (mesma disciplina do apto);  
2. estudo de razões com nível geral, COD, PRD e PRB nas metas IAAO **do tipo**;  
3. fundamentação registrada (hedônico e/ou ML conforme IBAPE 8.1.2);  
4. aprovação formal no `REGISTRO_ETAPAS_APROVACAO`.

Até lá, a referência assistida permanece o regime oficial da tipologia.

---

## 7. Benefícios e riscos

### Benefícios

- Responde à direção: **há especificação para todos os tipos**.  
- Mantém a linha segura do relatório: **não inventa grau normativo** onde não há amostra.  
- Alinha-se a IBAPE 7.1.3(a), 7.3.2, 7.6.2 e à prática IAAO de métodos por classe.  
- Reaproveita dado já disponível (`VLVENALCADASTRO` ~100%).  
- Separa claramente mercado validado × referência cadastral (transparência em impugnação).

### Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Confundir PGV com valor de mercado | Texto fixo na tela + código de regime no log |
| Usar venal como base automática de ITIV | Regime assistido; decisão humana; atenção ao Tema 1113/STJ |
| Defasagem do venal | Mostrar gap declarado×venal; não autuar só por esse gap no regime assistido |
| Duas regras (legado × modelo novo) | Unificar matriz neste documento e no avaliador |

---

## 8. Encaminhamentos

1. **Validar** esta proposta com Dilson (definição operacional de PGV; limiar de apto atípico; Casa/Loja assistido; Terreno individual).  
2. **Anexar** ao dossiê Selan como especificação de cobertura 100% das tipologias.  
3. **Implementar** o roteador de regimes no avaliador (substituir o “erro se não for apartamento”).  
4. **Agendar** diagnóstico Fase 2 (COD venal×venda e viabilidade de modelo próprio por tipo).  
5. **Apresentar** à direção com a mensagem: especificação completa agora; modelos próprios depois, se as metas fecharem.

---

## 9. Decisões solicitadas

| # | Decisão | Opções | Registro |
|---|---------|--------|----------|
| 1 | Adotar a referência assistida como especificação V1? | ( ) Sim ( ) Ajustar | |
| 2 | PGV = valor venal cadastral (`VLVENALCADASTRO`)? | ( ) Sim ( ) Outro: ___ | |
| 3 | Casa / Loja / Sala → `PGV_ASSISTIDO`? | ( ) Sim ( ) Ajustar | |
| 4 | Terreno e tipologias raras → `AVALIACAO_INDIVIDUAL`? | ( ) Sim ( ) Ajustar | |
| 5 | Anexo no pacote Selan nesta entrega? | ( ) Sim ( ) Depois | |
| 6 | Limiar de apartamento atípico/alto valor | ( ) Envelope p5–p95 ( ) Outro: ___ | |

**Aprovação da equipe:** ( ) Aprovado  ( ) Ajustar — _____________  
**Data:** ____/____/______  
**Responsáveis:** _______________________________

---

## 10. Referências

### Normas e padrões

1. ABNT NBR 14653-1:2019 — Avaliação de bens — Procedimentos gerais.  
2. ABNT NBR 14653-2:2011 — Avaliação de bens — Imóveis urbanos.  
3. IBAPE/SOBREA (2023) — Norma de avaliação em massa para fins tributários e de políticas urbanas.  
4. IAAO (2017) — *Standard on Mass Appraisal of Real Property*.  
5. IAAO (2013) — *Standard on Ratio Studies*.  

### Documentos internos do projeto

6. `FUNDAMENTACAO_NORMATIVA.md`  
7. `REGISTRO_ETAPAS_APROVACAO.md` (decisão de escopo 22/06/2026; aprovações Etapas 4–5 em 14/07/2026)  
8. `ESPECIFICACAO_REGIMES_POR_TIPOLOGIA.md`  
9. `Modelo_Apartamentos_Aprovado/LEIA-ME.md`  
10. `entrega_equipe_20260615/LEIA-ME.txt` (escopo V1 em camadas)

### Jurisprudência e literatura (contexto)

11. STJ — Tema 1113 (base de cálculo do ITBI = valor em condições normais de mercado; valor declarado e processo administrativo).  
12. Literatura comparada de avaliação tributária em Curitiba, São Paulo, Belo Horizonte e Rio de Janeiro (IPEA / LARES) — predominância do método evolutivo/PGV no IPTU.  
13. Estudos de atualização de PGV com métodos combinados / modelagem híbrida (geoestatística e aprendizado de máquina) na literatura técnica brasileira.  
14. IAAO — uso de abordagem de custo e técnicas alternativas de terreno na ausência de vendas suficientes.

---

*Documento elaborado para subsidiar alinhamento técnico e decisão da direção. Não substitui parecer jurídico formal nem a aprovação registrada no `REGISTRO_ETAPAS_APROVACAO`.*
