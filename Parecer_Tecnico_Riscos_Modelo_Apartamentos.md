# Parecer Técnico — Riscos do Modelo de Avaliação de Apartamentos (ITIV)

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**
**Referência:** Engenharia de Parâmetros (Etapas 1–7) e Lista Final de Parâmetros — Apartamentos
**Objetivo do documento:** apontar riscos identificados na revisão técnica, propor análises complementares para dimensioná-los e sugerir soluções antes do treino do modelo (Etapa 4).

---

## Como ler este documento

Cada risco é apresentado em três blocos: **o que é o risco** (explicação didática), **como medir** (análise a ser rodada antes de decidir) e **o que fazer** (solução proposta). Os riscos estão ordenados por criticidade — do que pode invalidar o propósito do modelo ao que é ajuste fino de qualidade.

---

## 1. Riscos Encontrados

### Risco 1 — Contaminação do alvo (a variável que queremos prever já contém o problema que queremos detectar)

**Explicação didática:** o modelo será treinado para aprender o padrão "características do imóvel → valor de mercado" usando como referência `VLTRANSACAO`, isto é, o valor que o contribuinte declarou na transação. Mas o próprio objetivo do sistema é encontrar contribuintes que declararam um valor distante do mercado — ou seja, declararam errado de propósito. Isso cria um paradoxo: se uma parcela relevante das transações de treino já é subdeclarada, o modelo aprende que aquele padrão de "imóvel bom, valor baixo" é normal, e passa a não sinalizar exatamente os casos que deveria pegar. É como treinar um detector de mentiras usando depoimentos que já contêm mentiras não identificadas como exemplo de "verdade".

Isso é diferente de outlier estatístico. Um outlier (ex.: venda de R$ 0,01) é fácil de identificar e remover. Subdeclaração "normal" (ex.: imóvel de R$ 500 mil declarado por R$ 400 mil) fica **dentro** da distribuição normal de preços e não é pega por nenhum critério estatístico como Chauvenet — ela se mistura ao ruído legítimo do mercado (negociação, urgência de venda, relação entre as partes, etc.).

### Risco 2 — Uso de estimativa pontual em decisão que deveria usar faixa de confiança

**Explicação didática:** o R² dos modelos diagnósticos ficou entre 0,50 e 0,70 — ou seja, o modelo explica de 50% a 70% da variação dos preços. Isso é um resultado tecnicamente bom para esse tipo de problema, mas significa que, para um imóvel específico, o valor previsto tem uma margem de erro considerável. Se o sistema simplesmente compara "valor declarado" contra "valor previsto pelo modelo" e sinaliza quando a diferença é grande, ele vai gerar falsos positivos: contribuintes que declararam corretamente, mas cujo imóvel tem alguma característica não capturada pelo modelo (reforma, vista, estado de conservação), ficarão marcados como suspeitos só porque a previsão pontual errou.

### Risco 3 — Duplicidade de transações sem trava técnica de deduplicação

**Explicação didática:** foram encontrados 13.239 registros que parecem ser a mesma venda repetida (mesma inscrição, data e valor, mesmas partes). A decisão registrada pela equipe (22/06/2026) foi **manter esses registros na base**; a regra de contar cada venda **uma única vez** no treino consta como **recomendação técnica ainda pendente de confirmação da equipe** — não como decisão tomada. O risco aqui tem duas camadas: a confirmação pendente e a possibilidade de essa deduplicação não ser aplicada de forma consistente no pipeline de treino. Se falhar, a mesma venda entra várias vezes, e o modelo passa a "achar" que aquele perfil de imóvel (e de preço) é mais comum do que realmente é, distorcendo a curva aprendida.

### Risco 4 — Regressividade vertical (COD/PRD/PRB fora da meta)

**Explicação didática:** existem três métricas padrão (usadas por órgãos de avaliação em massa, como o IAAO) para saber se um modelo de avaliação trata igual os imóveis baratos e os caros:

- **COD** mede a dispersão geral dos erros (precisão). Meta: ≤15%. Os modelos diagnósticos ficaram em 23,6%–25,3% — melhor que o valor venal atual (35,4%), mas ainda fora da meta.
- **PRD** compara a média das razões avaliação/venda com a razão agregada. Um valor acima de 1,03 indica que imóveis baratos tendem a ser **sobreavaliados proporcionalmente mais** que imóveis caros. Os modelos ficaram em 1,127–1,156 — pior que o valor venal atual (1,115).
- **PRB** é uma versão mais robusta do mesmo teste. Valores negativos abaixo de -0,05 confirmam a mesma distorção. Os modelos ficaram em -0,054 e -0,077 — também piores que o valor venal atual (-0,015).

Na prática: os três indicadores apontam na mesma direção — os modelos diagnósticos atuais tendem a avaliar proporcionalmente mais alto os imóveis baratos e proporcionalmente mais baixo os imóveis caros, e essa distorção é **maior** que a do sistema atual que está sendo substituído. Isso tem duas consequências: (1) risco de equidade tributária — contribuintes de imóveis mais baratos ficam mais expostos a sinalização indevida; (2) risco jurídico — a distorção sistemática é um argumento técnico forte para contestação em processo administrativo ou judicial.

> Nota: esses números são do modelo atual (treinado na base antiga), não do modelo novo com as decisões desta Lista Final. Ainda assim, a tendência regressiva já presente é um sinal de alerta que não deve ser assumido como "resolvido automaticamente" pelas melhorias de R².

### Risco 5 — Vazamento espacial no split treino/teste

**Explicação didática:** a divisão entre treino, validação e teste foi feita por sorteio aleatório. Para imóveis, isso é um problema sutil: apartamentos do mesmo prédio (ou de prédios muito próximos) têm características muito parecidas — mesma localização, mesma idade, muitas vezes o mesmo padrão construtivo. Se um sorteio aleatório colocar unidades do mesmo prédio em treino e em teste, o modelo não está sendo testado em algo realmente "novo" — ele já viu um "gêmeo" daquele imóvel no treino. Isso infla artificialmente as métricas de desempenho e esconde o quão bem o modelo realmente generaliza para prédios ou regiões que nunca viu.

### Risco 6 — Proxy de vizinhança (KNN) com risco residual de vazamento em validação/teste

**Explicação didática:** o proxy de localização por KNN usa a mediana de preço dos 10 imóveis mais próximos, excluindo o próprio imóvel do cálculo — isso já evita o erro mais óbvio (o imóvel "se prevendo"). Mas existe um erro mais sutil: se, ao calcular o proxy para um imóvel do conjunto de teste, os vizinhos usados incluírem outros imóveis também do teste (em vez de vir só do treino), o modelo está "espiando" informação que só deveria estar disponível depois — o que infla o desempenho medido em validação/teste sem representar o que acontece na produção real, quando não se tem o valor de venda de um imóvel novo.

### Risco 7 — Coeficiente de segurança definido sem análise de custo-benefício

**Explicação didática:** o "coeficiente de segurança" é a margem que decide a partir de que ponto uma diferença entre valor declarado e valor previsto é grande o suficiente para gerar sinalização. Definir esse número (ex.: 95%) sem uma análise que mostre quantos casos reais de subdeclaração passariam despercebidos naquele nível é decidir "no escuro". Um coeficiente muito conservador (para evitar autuar quem declarou certo) pode fazer o sistema não pegar praticamente nada de subdeclaração real; um coeficiente agressivo demais aumenta o risco de falsos positivos discutido no Risco 2.

### Risco 8 — Variável "andar da unidade" com baixa cobertura e possível viés de ausência

**Explicação didática:** apenas 35% dos registros têm informação de andar preenchida. A solução proposta (usar o valor quando existe, mais uma marca "tem/não tem informação") é uma boa prática, mas carrega um risco: a ausência dessa informação provavelmente não é aleatória — tende a se concentrar em cadastros mais antigos ou em bairros com processos de regularização menos completos. Nesse caso, a "marca de ausência" não está realmente informando algo sobre o andar do imóvel, e sim funcionando como um proxy disfarçado de "idade do cadastro" ou de região — o que pode confundir a interpretação do modelo e, em casos extremos, reintroduzir viés de localização por uma porta lateral.

### Risco 9 — Ausência de tratamento do tempo na base nova (vendas de 2019 a 2026 misturadas) *(acrescentado em 02/07/2026)*

**Explicação didática:** a base limpa nova contém vendas de dezembro/2018 a junho/2026, e a Lista Final de Parâmetros não tem **nenhuma variável de tempo**. Medição feita em 02/07/2026 (`medir_evolucao_temporal.py`): a mediana do R$/m² dos apartamentos subiu **+51% de 2021 a 2026** (de R$ 3.687 para R$ 5.570). Sem tratamento, o modelo mistura preços de épocas diferentes como se fossem o mesmo mercado — um apartamento vendido em 2021 por preço normal daquele ano pareceria "subdeclarado" aos olhos de um modelo dominado por preços de 2025/2026, e vice-versa. **Fato relevante:** o pipeline antigo (produção) já trata o tempo por três vias — deflação pelo IPCA (série 433 do Banco Central), divisão treino/validação/teste **por data** e variável de tendência temporal. O pipeline novo não herdou nenhuma delas ainda. A NBR 14653-2 exige dados contemporâneos ou homogeneizados à data de referência.

### Risco 10 — Escolha do tipo de modelo × exigências de fundamentação da norma *(acrescentado em 02/07/2026)*

**Explicação didática:** os diagnósticos usam dois tipos de modelo: a regressão hedônica (linear, explicável, com os testes estatísticos que a NBR 14653-2 usa para dar "grau de fundamentação" — significância, p-valor, etc.) e o LightGBM (não-linear, mais preciso, mas que não produz esses mesmos testes). Se o modelo final for o LightGBM, a defesa normativa não pode se apoiar nos testes clássicos da norma — precisa se apoiar no estudo de razões (IBAPE 7.8.1/IAAO) e na validação em amostra separada. Isso não impede o uso do LightGBM (o IBAPE/SOBREA 2023 admite técnicas computacionais), mas exige que a estratégia de fundamentação seja **decidida por escrito antes do treino**, para não descobrir depois que o modelo escolhido não tem a documentação exigida. Solução natural: manter os **dois modelos em paralelo** — o hedônico como âncora normativa e "fiscal" do LightGBM; divergência grande entre os dois em um imóvel vira alerta automático de avaliação individual.

---

## 2. Análises Propostas para Avaliar Melhor Cada Risco

| # | Risco | Análise proposta |
|---|-------|-------------------|
| 1 | Contaminação do alvo | Cruzar a base de transações com uma fonte de referência de maior confiança (ex.: avaliações bancárias de financiamento, quando disponíveis) para estimar quantas transações do treino têm indício de subdeclaração. Rodar o modelo diagnóstico separadamente incluindo e excluindo essas transações suspeitas, comparando o quanto a curva de preço muda. |
| 2 | Estimativa pontual vs. faixa | Calcular o intervalo de predição (não só o valor central) para cada imóvel usando os resíduos do modelo por faixa de valor, e simular quantos contribuintes seriam sinalizados usando o valor central vs. usando o limite inferior da faixa. |
| 3 | Duplicidade sem trava técnica | Escrever um teste automatizado que, antes de cada treino, verifique se o número de linhas únicas por `SQTRANSMISSAO`/grupo de duplicata bate com o esperado. Rodar essa checagem como parte do pipeline, não como verificação manual pontual. |
| 4 | Regressividade vertical | Recalcular COD, PRD e PRB **por decil de valor de venda** (não só agregado) para identificar exatamente em que faixa a distorção se concentra. Repetir a medição assim que o modelo novo (pós Lista Final) estiver treinado, antes de aprovar o resultado. |
| 5 | Vazamento espacial no split | Refazer a divisão treino/teste usando um esquema de separação por bloco espacial (ex.: por prédio ou por setor fiscal) e comparar o R²/COD obtidos nesse split com os do split aleatório atual. Diferença grande entre os dois indica vazamento. |
| 6 | Vazamento no proxy KNN | Auditar o código do cálculo do KNN para confirmar que, para qualquer imóvel de validação/teste, os vizinhos usados no cálculo pertencem exclusivamente ao conjunto de treino. Testar com um caso sintético controlado (imóvel de teste com valor "plantado" apenas nos vizinhos de teste) para confirmar que o proxy não muda. |
| 7 | Coeficiente de segurança sem custo-benefício | Construir uma curva de trade-off: para cada nível de coeficiente (ex.: 80%, 85%, 90%, 95%), medir quantos casos de subdeclaração conhecida (ou simulada) seriam detectados vs. quantos contribuintes corretos seriam sinalizados por engano. |
| 8 | Ausência de "andar" não aleatória | Comparar a distribuição de setor fiscal, idade de cadastro e faixa de preço entre os registros com e sem informação de andar. Testar o modelo com e sem a variável de andar para ver se a "flag de ausência" está carregando informação de localização/idade em vez de andar. |
| 9 | Tempo não tratado | Medir a evolução da mediana de R$/m² por ano (`medir_evolucao_temporal.py`) e decidir com a equipe a forma de homogeneização (deflação por índice, variável de tendência, ou ambas). |
| 10 | Tipo de modelo × norma | Registrar por escrito, antes do treino, a estratégia de fundamentação de cada modelo (hedônico: testes da NBR; LightGBM: estudo de razões + validação em amostra separada). |

---

## 3. Soluções Propostas

### Solução para o Risco 1 — Contaminação do alvo
Definir, antes do treino, um critério explícito de tratamento do alvo: (a) se houver fonte de maior confiança (avaliação bancária, laudo), priorizar essas transações como âncora de calibração; (b) na ausência disso, tratar o resultado do modelo como estimativa de **piso de mercado plausível**, nunca como valor "correto" — e documentar essa limitação no relatório de validação normativa, para que a interpretação do sinalizador leve isso em conta.

### Solução para o Risco 2 — Estimativa pontual vs. faixa
Adotar como regra de negócio que a sinalização de discrepância use o **limite inferior do intervalo de predição**, não a estimativa central. Isso já é parcialmente coberto pela previsão do "coeficiente de segurança", mas deve ser formalizado como requisito técnico do pipeline de inferência, não apenas como parâmetro ajustável depois.

### Solução para o Risco 3 — Duplicidade sem trava técnica
Implementar a deduplicação como etapa de código versionada e testada (não como instrução textual seguida manualmente), com um teste automatizado que bloqueia o treino se a contagem de linhas não bater com o esperado.

### Solução para o Risco 4 — Regressividade vertical
Tornar PRD e PRB **critérios formais de aprovação** do modelo final (com meta 0,98–1,03 e -0,05/+0,05, respectivamente), e não apenas métricas de acompanhamento. Se o modelo novo continuar fora da meta, testar: (a) ponderação por faixa de valor no treino; (b) modelagem do erro percentual em vez do valor em log; (c) segmentação do modelo por faixa de valor, caso a distorção esteja concentrada em uma ponta específica.

### Solução para o Risco 5 — Vazamento espacial no split
Adotar um esquema de validação cruzada espacial (block cross-validation) como validação complementar ao split aleatório atual, reportando as duas métricas lado a lado no relatório de validação normativa — isso dá uma visão mais realista do desempenho do modelo em regiões não vistas.

### Solução para o Risco 6 — Vazamento no proxy KNN
Formalizar por escrito, no pipeline, a regra "vizinhos do KNN sempre vêm exclusivamente do conjunto de treino" e incluir essa regra como item de checklist na etapa de treino (Etapa 4), com teste automatizado equivalente ao proposto na análise.

### Solução para o Risco 7 — Coeficiente de segurança
Substituir a decisão de coeficiente fixo (ex.: 95% "por precaução") por uma decisão baseada na curva de custo-benefício da análise proposta, escolhendo o ponto que equilibra explicitamente o risco de autuação indevida contra o risco de deixar passar subdeclaração real — com essa escolha registrada e justificada no processo de aprovação.

### Solução para o Risco 8 — Ausência de "andar" não aleatória
Manter a estratégia de "valor + flag de ausência" apenas se a análise de distribuição confirmar que a ausência não está simplesmente replicando o efeito de localização/idade já capturado por outras variáveis. Caso a análise confirme essa sobreposição, considerar remover a variável "andar" da lista final ou usá-la apenas como variável auxiliar de baixa importância, sem risco de reintroduzir viés geográfico por via indireta.

### Solução para o Risco 9 — Tempo não tratado *(acrescentado em 02/07/2026)*
Levar à equipe a decisão sobre a forma de homogeneização temporal, com três opções técnicas conhecidas (e já praticadas no pipeline antigo): (a) deflação dos valores por índice de preços (IPCA, série 433 do BCB) até a data de referência; (b) variável de tendência temporal no modelo; (c) combinação das duas. Nenhuma das opções deve ser adotada sem registro formal da escolha.

### Solução para o Risco 10 — Tipo de modelo × norma *(acrescentado em 02/07/2026)*
Manter os dois modelos em paralelo (hedônico como âncora normativa; LightGBM como refinamento), registrar por escrito a estratégia de fundamentação de cada um antes do treino, e usar a divergência entre os dois como alerta automático de avaliação individual.

---

## 4. Adendo — Análises executadas em 02/07/2026

As ferramentas abaixo foram criadas e executadas; nenhum dado foi alterado.

| Ferramenta | O que faz | Resultado da primeira execução |
|---|---|---|
| `verificacoes_pre_treino.py` | Travas que **bloqueiam o treino** se houver duplicata, sobreposição treino/teste ou dedup pendente | **BLOQUEADO (proposital)**: 6 IDs repetidos no treino; **6 transações presentes ao mesmo tempo no treino e na validação/teste** (vazamento real — os 12 `SQTRANSMISSAO` duplicados da pendência da Etapa 1 caíram em conjuntos diferentes); 6.129 linhas de venda repetida no treino aguardando decisão de dedup |
| `gerar_manifesto_treino.py` | Congela a "impressão digital" (SHA-256) da base, das amostras e dos scripts em `manifesto_treino.json` | Manifesto gerado — qualquer alteração futura em dados ou código será detectável |
| `comparar_split_espacial.py` | Compara divisão aleatória × por bloco de prédio (mesmo modelo diagnóstico das Etapas 5/7) | **O receio do Risco 5 não se confirmou**: erro mediano praticamente igual (18,4% aleatório × 18,2% por prédio); nenhum sinal de inflação por "gêmeos de prédio". O sorteio aleatório da Etapa 1 mostrou-se defensável |
| `metricas_iaao_por_decil.py` | COD/PRD/PRB por decil de valor — pronto para o modelo novo pós-treino | Demonstração com o valor venal atual: vendas simbólicas (R$ 0,01) concentram-se no 1º decil e explodem as métricas de média; razão mediana de 0,85–0,91 nos decis 2–4 |
| `medir_evolucao_temporal.py` | Mede a evolução da mediana de R$/m² por ano | **+51% de 2021 a 2026** (R$ 3.687 → R$ 5.570) — dimensiona o Risco 9 |
| Auditoria do KNN (Etapa 7) | Leitura do código do proxy de vizinhança | O cálculo diagnóstico exclui o próprio imóvel, mas usa vizinhos da base inteira — aceitável para a correlação medida na Etapa 7; a regra "vizinhos só do treino" **ainda não existe em código** e deve ser requisito da Etapa 4 (consta no checklist da trava) |

---

## Resumo Executivo

| Risco | Criticidade | Bloqueia treino? |
|-------|-------------|-------------------|
| 1. Contaminação do alvo | Crítica | Recomendado resolver antes |
| 4. Regressividade vertical (COD/PRD/PRB) | Crítica | Recomendado medir no modelo novo antes de aprovar |
| 9. Tempo não tratado (+51% de 2021 a 2026) | Crítica | Deve ser decidido antes do treino |
| 2. Estimativa pontual vs. faixa | Alta | Pode ser regra de inferência, não bloqueia treino |
| 3. Duplicidade sem trava técnica | Alta | **Trava criada e ativa** — treino bloqueado até a equipe decidir a dedup |
| 10. Tipo de modelo × norma | Alta | Estratégia de fundamentação deve ser registrada antes do treino |
| 5. Vazamento espacial no split | Média-alta | **Medido em 02/07/2026 — não se confirmou** (erro mediano 18,4% × 18,2%) |
| 6. Vazamento no proxy KNN | Média-alta | Auditado — regra "vizinhos só do treino" é requisito de código da Etapa 4 |
| 7. Coeficiente de segurança sem custo-benefício | Média | Pode ser refinado após o treino, antes da produção |
| 8. Ausência de "andar" não aleatória | Baixa-média | Pode ser avaliado em paralelo ao treino |

Este parecer não substitui a decisão da equipe registrada nos documentos de aprovação — é uma camada adicional de verificação técnica para subsidiar essa decisão antes da Etapa 4 (Treino do modelo).
