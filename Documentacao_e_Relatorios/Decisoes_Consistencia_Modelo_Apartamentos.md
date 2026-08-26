# Decisões de Consistência — Modelo de Apartamentos (ITIV)

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**
**Data:** 02/07/2026
**Complementa:** Parecer Técnico de Riscos e REGISTRO_ETAPAS_APROVACAO
**Objetivo:** reunir, em um só lugar, as decisões que a equipe precisa tomar **antes do treino** (Etapa 4) para que o modelo seja consistente — mesmo resultado ao rodar de novo, bom desempenho em imóveis nunca vistos e tratamento igual para imóveis baratos e caros.

---

## Como ler

Cada item traz: **o fato medido** (sem interpretação), **por que importa** e **a decisão em aberto** com opções. Nada foi alterado nos dados — as ferramentas criadas em 02/07/2026 apenas medem e travam.

---

## D1. Os 12 `SQTRANSMISSAO` duplicados causaram vazamento real entre treino e teste

**Fato medido** (`verificacoes_pre_treino.py`): os 12 registros com o mesmo número de transmissão (pendência da Etapa 1) caíram em conjuntos diferentes no sorteio — **6 transações estão ao mesmo tempo no treino e na validação/teste**. Isso significa que o teste contém cópias de vendas que o modelo viu no treino.

**Por que importa:** qualquer métrica medida na validação/teste fica contaminada enquanto isso existir.

**Decisão da equipe:**
( ) Remover os duplicados de `SQTRANSMISSAO` mantendo a 1ª ocorrência e **refazer a divisão** treino/validação/teste (recomendado — era a proposta da pergunta 1 da Etapa 2)
( ) Outra: ____________________

## D2. Confirmar a deduplicação de venda repetida (inscrição+data+valor) no treino

**Fato medido:** o arquivo de treino atual contém **6.129 linhas** que repetem a mesma venda (mesma inscrição, data e valor). A recomendação técnica registrada em 22/06/2026 — manter na base, contar uma vez no treino — está **pendente de confirmação**.

**Por que importa:** venda contada 2× ou 3× pesa 2× ou 3× na curva que o modelo aprende. A trava T5 do `verificacoes_pre_treino.py` **bloqueia o treino** até isso ser resolvido.

**Decisão da equipe:**
( ) Confirmar: contar cada venda uma única vez no treino (base completa permanece intacta para auditoria)
( ) Outra: ____________________

## D3. Como tratar o tempo (Risco 9 do Parecer)

**Fato medido** (`medir_evolucao_temporal.py`): a mediana do R$/m² dos apartamentos subiu **+51% de 2021 a 2026** (R$ 3.687 → R$ 5.570). A base nova mistura vendas de dez/2018 a jun/2026 e a Lista Final de Parâmetros não tem variável de tempo. O pipeline antigo (produção) já tratava o tempo por três vias: deflação IPCA (série 433/BCB), divisão por data e variável de tendência.

**Por que importa:** sem tratamento, o modelo confunde "imóvel barato" com "venda antiga". A NBR 14653-2 pede dados contemporâneos ou homogeneizados à data de referência.

**Decisão da equipe:**
( ) Deflação por IPCA até a data de referência (como o pipeline antigo)
( ) Variável de tendência temporal no modelo
( ) As duas (deflação + tendência)
( ) Outra: ____________________

## D4. Metas de equidade (COD/PRD/PRB) como condição formal de aprovação

**Fato já registrado** (Etapa 6): os modelos diagnósticos ficaram fora da meta de uniformidade vertical (PRD 1,127–1,156 contra meta 0,98–1,03; PRB −0,054/−0,077 contra meta ±0,05), piores que o valor venal atual nesses indicadores.

**Ferramenta pronta:** `metricas_iaao_por_decil.py` calcula COD/PRD/PRB **por faixa de valor** para o modelo novo assim que ele for treinado.

**Decisão da equipe:**
( ) Adotar as metas IAAO (razão 0,90–1,10; COD ≤ 15% ou, transitoriamente, ≤ o valor atual; PRD 0,98–1,03; PRB ±0,05) como **condição de aprovação** do modelo novo — modelo fora da meta volta para ajuste
( ) Manter as metas apenas como acompanhamento
( ) Outra: ____________________

## D5. Sinalização pelo limite inferior da faixa (não pelo valor central)

**Fato já registrado** (Etapa 6 + Parecer, Risco 2): o erro individual do modelo é considerável (COD ~24% nos diagnósticos). O coeficiente de segurança (proposta de 95%) será reavaliado com o COD do modelo novo em mãos (decisão de 22/06/2026).

**Decisão da equipe:**
( ) Formalizar como **requisito do pipeline de inferência**: a comparação com o valor declarado usa o limite inferior do intervalo de predição, e o coeficiente final sai da curva de custo-benefício (análise 7 do Parecer), não de um número fixado de antemão
( ) Outra: ____________________

## D6. Dois modelos em paralelo (fundamentação normativa — Risco 10)

**Fato:** o hedônico produz os testes estatísticos que a NBR 14653-2 usa para o grau de fundamentação; o LightGBM não produz esses testes, e sua defesa se apoia no estudo de razões (IBAPE 7.8.1/IAAO) e na validação em amostra separada.

**Decisão da equipe:**
( ) Treinar e manter os dois; o hedônico é a âncora normativa e a divergência grande entre os dois em um imóvel gera alerta de avaliação individual; registrar por escrito a estratégia de fundamentação de cada um **antes** do treino
( ) Seguir só com um modelo — qual e com qual fundamentação: ____________________

## D7. Registro da decisão sobre o esquema de divisão treino/teste

**Fato medido** (`comparar_split_espacial.py`, 02/07/2026): a comparação entre sorteio aleatório e divisão por bloco de prédio deu erro mediano praticamente igual (18,4% × 18,2%) — **não se confirmou** a inflação temida no Risco 5. Registro adicional: o pipeline antigo usava divisão **por data** (treino até jun/2025, teste a partir de jan/2026), que simula o uso real — prever vendas futuras.

**Decisão da equipe:**
( ) Manter o sorteio aleatório da Etapa 1 (defensável pelo diagnóstico), refeito após D1/D2
( ) Adotar divisão por data como no pipeline antigo (mais próxima do uso em produção)
( ) Aleatório como principal + medição por data em paralelo no relatório de validação
( ) Outra: ____________________

---

## Regras já transformadas em código (não dependem de decisão — já valem)

| Ferramenta | Função |
|---|---|
| `verificacoes_pre_treino.py` | Bloqueia o treino se houver ID duplicado, sobreposição treino/teste ou dedup pendente (rodar SEMPRE antes de treinar) |
| `gerar_manifesto_treino.py` | Congela a impressão digital (SHA-256) de dados e scripts em `manifesto_treino.json` (regerar após D1/D2 e guardar com o modelo) |
| `metricas_iaao_por_decil.py` | COD/PRD/PRB por decil — pronto para o modelo novo |
| `medir_evolucao_temporal.py` | Medição da evolução de preços por ano |
| `comparar_split_espacial.py` | Diagnóstico aleatório × bloco de prédio (reproduzível, semente 42) |

**Requisito de código para a Etapa 4 (treino), já constando do checklist da trava:**
- Chauvenet/limites de saneamento: **somente no treino** (IBAPE 7.6.7/7.9.1);
- Proxy KNN de vizinhança: vizinhos **exclusivamente do conjunto de treino**;
- Registrar semente, versões e manifesto junto com o modelo treinado.

---

*Este documento organiza decisões — não decide. Cada item aguarda a marcação da equipe, no mesmo formato dos documentos de aprovação anteriores.*
