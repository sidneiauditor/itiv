# Arquitetura técnica — ITIV

**Sistema:** avaliação em massa de imóveis para o Imposto sobre Transmissão de Imóveis (ITIV)  
**Órgão:** Coordenadoria de Inteligência Fiscal — SEFAZ Salvador  
**Escopo em produção:** apartamentos com compra e venda registrada  
**Modelo vigente:** LightGBM com idade + inscrição relativa (promovido em 26/08/2026)  
**Repositório:** código e documentação; os artefatos de dados (Parquet, Excel, modelo serializado) ficam no ambiente de trabalho da equipe e, em geral, **não** estão versionados neste clone.

Este documento descreve o funcionamento técnico da solução a partir do código. Complementa, sem substituir, os dossiês normativos em `Documentacao_e_Relatorios/` e `Modelo_Apartamentos_Aprovado/decisoes_e_aprovacao/`.

---

## 1. Visão geral

O ITIV **não** é uma aplicação web corporativa com API REST, banco relacional e frontend SPA. É um **ecossistema analítico offline-first** composto por quatro camadas:

| Camada | Papel |
|--------|--------|
| **Pipeline batch (Python)** | Limpeza da base ITIV, engenharia de parâmetros, treino, validação normativa e classificação operacional em lote |
| **Artefatos versionados em arquivo** | Parquet, CSV, JSON, pickle e booster LightGBM em texto (`.txt`) |
| **Avaliador local** | Servidor HTTP mínimo (`127.0.0.1:8766`) para o auditor consultar uma transmissão ou um imóvel do cadastro |
| **Relatórios** | Scripts Python e Node.js que geram dossiês Word/Excel para a equipe e para o Selan |

O desenho é deliberado: o valor estimado é **subsídio técnico**; a decisão fiscal permanece humana. Não há autenticação, fila, orquestração nem deploy em nuvem. O alvo operacional é a estação Windows da equipe fiscal.

### Princípio normativo que governa a arquitetura

Limites, filtros de plausibilidade e saneamento de outliers aplicam-se **somente à amostra de treino**. A inferência cobre **todos** os apartamentos consultáveis, sem exclusão silenciosa (IBAPE 7.6.7 e 7.9.1). Imóveis atípicos devem ser **sinalizados** para avaliação individual (IBAPE 7.1.3a), não descartados.

Fontes: `Documentacao_e_Relatorios/PROJETO_Conformidade_Normas_Avaliacao.md` e `Modelo_Apartamentos_Aprovado/codigo/construir_base_limpa.py`.

### Duplo modelo

Toda estimativa operacional combina:

1. **LightGBM** — modelo de uso (previsão de `log(valor deflacionado)`).  
2. **Hedônico OLS** (`statsmodels`) — âncora normativa da NBR 14653-2 (testes t/F, grau de fundamentação). Não substitui o LightGBM; serve de segunda opinião e de objeto da Etapa 5.

---

## 2. Contexto e normas de referência

| Norma | Uso na solução |
|-------|----------------|
| ABNT NBR 14653-1:2019 | Procedimentos gerais de avaliação |
| ABNT NBR 14653-2:2011 | Imóveis urbanos; Chauvenet (anexo B.3); pressupostos do hedônico (anexo A) |
| IBAPE/SOBREA 2023 | Avaliação em massa tributária (amostra × universo, métricas, memorial) |
| IAAO Ratio Studies 2013 / Mass Appraisal 2017 | COD, PRD, PRB, estudo de razões |

Metas de qualidade usadas no holdout (residencial):

- **COD** ≤ 15%  
- **PRD** entre 0,98 e 1,03  
- **PRB** entre −0,05 e +0,05  
- **Nível geral** (mediana da razão estimado/preço) entre 0,90 e 1,10 (Grau III IBAPE)

Holdout do modelo promovido (`Modelo_Apartamentos_Aprovado/LEIA-ME.md`):

| Métrica | Valor |
|---------|------:|
| COD mediano | 6,383% |
| COD | 9,231% |
| PRD | 1,0157 |
| PRB | −0,0084 |

---

## 3. Estrutura do repositório

```
itiv/
├── Modelo_Apartamentos_Aprovado/     # PRODUÇÃO (promovido 26/08/2026)
│   ├── app/avaliador_web_apartamentos.py
│   ├── codigo/                       # biblioteca ML + etapas 4 e 5 + lote
│   ├── decisoes_e_aprovacao/         # decisões da equipe
│   ├── dados/                        # artefatos (ausentes neste clone Git)
│   └── Avaliador Apartamentos.bat
├── Modelo_Apartamentos_Candidato_Idade_20260811/  # pacote Selan (origem da promoção)
├── desafiante_idade/                 # laboratório; não altera produção sozinho
├── Documentacao_e_Relatorios/        # normas, registro de etapas, regimes
├── Scripts_Auxiliares/               # etapas 1–3, diagnósticos, relatórios
└── arquitetura.md                    # este documento
```

### Papel de cada pasta

| Pasta | Responsabilidade |
|-------|------------------|
| `Modelo_Apartamentos_Aprovado/` | Código e contratos do modelo em produção; avaliador HTML; scripts de lote e status |
| `Modelo_Apartamentos_Candidato_Idade_20260811/` | Snapshot do candidato `idade_mais_rel` enviado ao Selan |
| `desafiante_idade/` | Experimentos (idade, SELIC, KNN) e script de **promoção** para produção |
| `Documentacao_e_Relatorios/` | Fundamentação normativa e registro de aprovação |
| `Scripts_Auxiliares/` | Etapa 1 (split 80/10/10), Etapa 2 (consistência), Etapa 3 (outliers), utilitários |

### Dependência externa (fora deste repositório)

O avaliador e vários scripts de lote importam `src.config` e `src.limpeza` de:

```
entrega_equipe_20260615/
```

Esse pacote legado concentra: nomes de colunas do Excel ITIV, cache da base bruta, série IPCA e deflação. Sem ele, o avaliador não sobe.

Outros caminhos esperados no ambiente da equipe (paths típicos `D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\`):

- `Informações ITIV 20260610.xlsx` — extração bruta (~148 mil transmissões)  
- `base_limpa_normas.parquet` — Etapa 0  
- `amostras/` — splits e parâmetros  
- `projeto_itiv/Imoveis Salvador.xlsx` — cadastro municipal (avaliação sem transmissão)

### Arquivos órfãos na raiz

`LEIA-ME.txt`, `Executar.bat` e `Instalar dependências.bat` referem-se a um **TranscritorAI** (Whisper). Não fazem parte do ITIV.

---

## 4. Stack tecnológica

| Camada | Tecnologia |
|--------|------------|
| Linguagem | Python 3.11+ |
| ML | LightGBM, scikit-learn (GridSearch, RF, Extra Trees, HistGBM, ElasticNet) |
| Estatística / hedônico | statsmodels (OLS), scipy (Chauvenet, testes da Etapa 5) |
| Dados | pandas, numpy, pyarrow (Parquet), openpyxl / xlsxwriter |
| Geo | pyproj (UTM → WGS84), sklearn `NearestNeighbors`, `BallTree` (haversine) |
| Explicabilidade | SHAP (opcional, memória de cálculo no avaliador) |
| Web | `http.server.HTTPServer` (stdlib), HTML/CSS inline, Leaflet via CDN |
| Relatórios Word | Node.js + pacote `docx`; também `python-docx` no desafiante |
| APIs | BCB SGS 433 (IPCA), BCB SGS 432 (SELIC, só experimental), Google Geocoding e Street View |
| Persistência | **Somente arquivos** — não há banco de dados |
| SO alvo | Windows (`.bat`, paths absolutos) |

Não há `requirements.txt` na raiz, Docker, CI nem gerenciador de pacotes do projeto. As dependências são implícitas nos imports.

---

## 5. Modelo de domínio

### Entidades

| Entidade | Identificador | Descrição |
|----------|---------------|-----------|
| Transmissão ITIV | `SQTRANSMISSAO` | Registro de transação (compra e venda, etc.) |
| Imóvel cadastral | `CDINSCRICAOIMOB` | Inscrição imobiliária municipal |
| Tipologia | `DSSUBUNIDADE` | Apartamento, Casa, Loja, … — o ML cobre só Apartamento |
| Setor fiscal | `CDSETORFISCAL` | Segmentação geográfica/administrativa |
| Transação | `VLTRANSACAO`, `DATA_TRANSACAO` | Valor declarado e data (DTPAGAMENTO com fallbacks) |
| Valor deflacionado | `VLTRANSACAO_DEFLACIONADO` | Valor em moeda da data de referência (IPCA SGS 433) |
| Valor venal | `VLVENALCADASTRO` / `VLVENALCORRIGIDO` | Referência cadastral; **não entra como preditor** (circularidade) |
| Idade | `AACONSTRUCAO` → `IDADE_NA_TRANSACAO_IMP` | Ano de construção + flags de ausência/invalidade |
| Inscrição relativa | `LOG_INSCRICAO_REL`, `RANK_INSCRICAO_SETOR` | Posição da inscrição no setor (stats só do treino) |
| Status operacional | ver § 10 | Compatível / Auditor / Suspeito / Fora de escopo |

### Relacionamentos

```
CDINSCRICAOIMOB  1 ──< N  SQTRANSMISSAO
CDSETORFISCAL    1 ──< N  imóveis / transmissões
Nascimento_Imovel.csv  1:1  CDINSCRICAOIMOB  (ano de construção)
POOL de treino ──► stats de inscrição relativa ──► inferência
POOL de treino ──► KNN_PROXY causal (k = 10)
```

### Features de produção (modelo promovido)

**9 parâmetros base** (`codigo/apartamentos_lib.py` — `FEATURES_LGBM`):

- `LOG_AREA` — ln da área privativa (`VLAREAUSOPRIV`)  
- `NUPAVIMENTOS` — pavimentos do prédio  
- `ANDAR_UNIDADE` + `FLAG_ANDAR_AUSENTE`  
- `VAR_TENDENCIA` — meses entre a venda e a data de referência do IPCA  
- `VLCOORDGEOX`, `VLCOORDGEOY` — coordenadas cadastrais  
- `CDSETORFISCAL` — categórica no LightGBM  
- `KNN_PROXY` — média do log(R$/m²) dos 10 vizinhos no pool de treino  

**Idade** (`codigo/idade_features.py` — `FEATURES_IDADE`):

- `IDADE_NA_TRANSACAO_IMP`  
- `FLAG_ANO_AUSENTE`  
- `FLAG_ANO_INVALIDO`  

**Inscrição relativa** (`codigo/inscricao_relativa.py` — `FEATURES_REL`):

- `LOG_INSCRICAO_REL` = log1p(inscrição) − mediana do setor no treino  
- `RANK_INSCRICAO_SETOR` — percentil empírico da inscrição no setor (0–1)  

A lista efetiva da inferência é lida de `dados/features_producao.json`. Medianas de imputação vêm de `dados/fill_medians_producao.json`.

**Explicitamente fora do modelo:** áreas construídas redundantes, fatores `VLFC*` e valor venal como preditor (circularidade com a PGV). A idade, que na lista de 09/07/2026 saía por falta de dado, entrou em 26/08/2026 via `Nascimento_Imovel.csv`.

---

## 6. Pipeline de modelagem (Etapas 0 a 5)

O fluxo é **sequencial e manual**: cada script é executado pela equipe após aprovação da etapa anterior (`Documentacao_e_Relatorios/REGISTRO_ETAPAS_APROVACAO.md`).

```
Excel bruto ITIV (~148.811 transmissões)
        │
        ▼
Etapa 0  construir_base_limpa.py
        → base_limpa_normas.parquet  (121.932 linhas)
        │
        ▼
Etapa 1  Scripts_Auxiliares/etapa1_dividir_amostra.py
        → treino / validacao / teste  (80/10/10, semente 42)
        │
        ▼
Etapa 2  Scripts_Auxiliares/validar_consistencia.py
        → só mede (faltantes, duplicatas, extremos); não exclui
        │
        ▼
Etapa 3  Scripts_Auxiliares/etapa3_comparar_outliers.py
        → Chauvenet vs IQR vs Z vs Mahalanobis (comparação)
        │
        ▼
Etapa 4.1  preparar_base_treino.py     filtros D1–D3 + split 80/20 apartamentos
Etapa 4.2  engenharia_parametros_treino.py
Etapa 4.3  saneamento_chauvenet_iterativo.py   (só treino / fold)
Etapa 4.4  treinar_modelo_apartamentos.py      GridSearch + CV k=10 + holdout
        │
        ▼
        modelo_lightgbm_apartamentos.txt
        │
        ▼
Etapa 5  etapa5_validacao_normativa.py
        → pressupostos hedônico + IAAO (não altera dados)
        │
        ▼
Avaliador web  +  lote Excel  +  status operacional
```

### 6.1 Etapa 0 — Base limpa

Arquivo: `Modelo_Apartamentos_Aprovado/codigo/construir_base_limpa.py`.

Critérios (IBAPE 7.2.11 + decisões da equipe):

1. Situação ∈ {Baixado, Liberado, Em aberto} (exclui Cancelado)  
2. Tipo ∈ {`Compra e Venda`, `Compra e venda de garagem`} — igualdade exata  
3. Data: `DTPAGAMENTO`; se inválida, registro / lavratura / assinatura; janela 2004–2026  
4. Fração transmitida = 100% (`VLFRACAOTERRENO == 1,0`)  
5. `VLTRANSACAO > 0`  

Não aplica limite de área nem de R$/m².

### 6.2 Etapa 1 — Split da base limpa

Arquivo: `Scripts_Auxiliares/etapa1_dividir_amostra.py`.  
Partição aleatória 80/10/10, semente **42** (IBAPE 7.6.4 e 7.8.4).  
Essa divisão é da **base limpa completa** (todas as tipologias). O recorte de apartamentos para o modelo ocorre na Etapa 4.1.

### 6.3 Etapa 4.1 — Amostra de treino de apartamentos

Arquivo: `Modelo_Apartamentos_Aprovado/codigo/preparar_base_treino.py`.

Sobre a base limpa, **somente Apartamento**:

| Código | Regra |
|--------|--------|
| D1 | Remove `SQTRANSMISSAO` duplicado (mantém a 1ª ocorrência) |
| Filtro equipe (14/07/2026) | Tipo exatamente `Compra e Venda`; `VLITIV > 0`; desvio \|transação − venal corrigido\| / venal ≤ 30% |
| D2 | Remove duplicata inscrição + data + valor |
| D3 | Exclui vendas anteriores a 01/03/2020; deflaciona pelo IPCA; cria `VAR_TENDENCIA` |

Depois: **80% pool** (treino/CV) e **20% teste final (holdout)**, semente 42. O holdout **nunca** entra em ajuste de hiperparâmetros.

Deflação: série 433 do SGS/BCB; índice acumulado com base 100 no último mês publicado. Transações em meses ainda não publicados recebem índice 100.

### 6.4 Etapa 4.2 — Engenharia de parâmetros

Arquivo: `Modelo_Apartamentos_Aprovado/codigo/engenharia_parametros_treino.py`.

Gera `pool_treino_parametros.parquet` e `teste_final_parametros.parquet` com as colunas da lista aprovada em 09/07/2026. Remove linhas sem área privativa válida (sem `LOG_AREA` o modelo não opera). Idade e inscrição relativa são anexadas **depois**, no fluxo desafiante / produção.

### 6.5 Etapa 4.3 — Chauvenet iterativo

Arquivo: `Modelo_Apartamentos_Aprovado/codigo/saneamento_chauvenet_iterativo.py`.

Aplica-se a `log(R$/m²)` **somente no treino de cada fold** (e no GridSearch sobre o pool). Remove o ponto mais distante da média enquanto violar o limiar de Chauvenet (`√2 · erfcinv(1/(2n))`), recalcula média/desvio, repete. Grupos com menos de 5 pontos não são saneados.

### 6.6 Etapa 4.4 — Treino

Arquivo: `Modelo_Apartamentos_Aprovado/codigo/treinar_modelo_apartamentos.py`.

Três fases:

**A — GridSearch multi-modelo** (CV interno k=5 no pool já saneado + KNN):

- LightGBM, HistGradientBoosting, Random Forest, Extra Trees, ElasticNet  
- Critério: menor MAE no log do valor  
- LightGBM trata `CDSETORFISCAL` como categórica  

**B — Validação cruzada externa k=10:** em cada fold, Chauvenet e `KNN_PROXY` são **recalculados só com o treino do fold** (sem vazamento). Treina hedônico OLS e o vencedor da fase A; mede no fold de validação.

**C — Treino final no pool inteiro** e **uma única** avaliação no holdout.

Alvo: `y = log(VLTRANSACAO_DEFLACIONADO)`. Predição operacional: `exp(log_pred)`.

O GridSearch (fase A) roda uma vez no pool por custo; os folds externos isolam Chauvenet e KNN.

### 6.7 Etapa 5 — Validação normativa

Arquivo: `Modelo_Apartamentos_Aprovado/codigo/etapa5_validacao_normativa.py`.

Só mede; não grava modelo novo.

- **Bloco 1:** pressupostos do hedônico (NBR 14653-2 anexo A) — F, t, normalidade, homocedasticidade, Durbin–Watson, VIF, influenciantes  
- **Bloco 2:** grau de fundamentação e precisão do hedônico (tabelas da NBR). O LightGBM, por não ser especificação clássica, exige justificativa (IBAPE 8.1.2)  
- **Bloco 3:** razões IAAO por decil de valor e por setor no holdout  
- **Extra:** venal × hedônico × LightGBM  

Setores 177→175 e 179→162 são agrupados **somente na especificação hedônica** (micronumerosidade).

### 6.8 KNN proxy causal

Função: `apartamentos_lib.calcular_knn_proxy`.

Para cada imóvel-alvo, média do `log(R$/m²)` dos **k=10** vizinhos mais próximos **no conjunto de treino**, em coordenadas X/Y. Se treino e alvo são o mesmo DataFrame, busca k+1 vizinhos e **descarta o mais próximo** (o próprio ponto). Na inferência, a base de vizinhos é sempre o **POOL de treino**, nunca a transação avaliada.

---

## 7. Fluxo desafiante e promoção

A pasta `desafiante_idade/` é o laboratório. **Não altera** `Modelo_Apartamentos_Aprovado/` até a promoção explícita.

### 7.1 Pipeline experimental

`desafiante_idade/pipeline_idade_apartamentos.py`:

- Diagnóstico Compatível × idade / inscrição (planilha de status operacional)  
- Treino desafiante com hiperparâmetros congelados do LightGBM vencedor (`num_leaves=63`, `n_estimators=800`, `learning_rate=0.05`, `min_child_samples=20`)  
- CV k=5 (mais leve que k=10 da produção)  
- Testes laterais: inscrição relativa vs idade (`teste_inscricao_vs_idade.py`), SELIC (`teste_selic_lags.py`), KNN da idade (`teste_knn_idade.py`)

A SELIC (SGS 432) **não** entrou em produção.

### 7.2 Pacote candidato

`Modelo_Apartamentos_Candidato_Idade_20260811/` é o snapshot enviado ao Selan (`idade_mais_rel`). Alternativa quase empatada: `idade_abs_rel` (idade + inscrição absoluta + relativa).

Efeito operacional reportado: nos imóveis “antigos” (inscrição &lt; 300 mil), Compatível (±15%) sobe de ~74% para ~81%.

### 7.3 Promoção para produção

`desafiante_idade/promover_candidato_producao.py`:

1. Arquiva o LightGBM de 14/07/2026 em `dados/legado_v20260714/`  
2. Copia modelo, features JSON, medianas, nascimento, stats de inscrição, holdout e módulos Python  
3. Calcula SHA-256 dos artefatos e grava `dados/registro_promocao_idade_rel.json`  
4. **Não** altera o avaliador HTML (feito em commit separado)

Nome operacional do booster permanece `modelo_lightgbm_apartamentos.txt` para o avaliador não mudar de caminho.

---

## 8. Avaliador web (runtime de inferência)

### 8.1 Inicialização

Launcher: `Modelo_Apartamentos_Aprovado/Avaliador Apartamentos.bat`  
Processo: `app/avaliador_web_apartamentos.py`  
Bind: `127.0.0.1:8766`

No startup (~1 minuto) carrega em memória:

| Recurso | Origem |
|---------|--------|
| Base bruta ITIV | `src.limpeza.carregar_ou_cachear_bruto()` |
| Tabela de modelagem | Parquet do pacote legado (valor deflacionado, lat/lon derivados) |
| Pool de treino | `dados/amostras/pool_treino_parametros.parquet` |
| Modelo LightGBM | texto → `lgb.Booster(model_str=...)` (evita path com acento no Windows) |
| Hedônico | treinado no pool na inicialização |
| Features / medianas | JSON de produção |
| Nascimento | `dados/Nascimento_Imovel.csv` |
| Stats inscrição | Parquet + pickle `vals_inscricao_por_setor.pkl` |
| Quantis IC 80% | razões do holdout promovido (p10 e p90) |
| Cadastro | `projeto_itiv/Imoveis Salvador.xlsx` (ou Parquet cache) |

Não há workers nem recarregamento a quente.

### 8.2 Rotas HTTP

| Rota | Função |
|------|--------|
| `GET /avaliar` | Formulário de busca por SQ ou inscrição |
| `GET /avaliar?q=` | Avaliação de transmissão; se a inscrição tiver várias SQs, lista-as |
| `GET /cadastro` | Formulário de inscrição cadastral (sem transmissão) |
| `GET /cadastro?q=` | Compara venal × mercado “hoje” (`VAR_TENDENCIA = 0`) |
| `GET /geocode?lat=&lon=` | Proxy JSON do Geocoding reverso Google |
| `GET /streetview?lat=&lon=` | Proxy JPEG do Street View Static |

A UI é HTML gerado no servidor (duas abas: Transmissão e Cadastro). Mapa: Leaflet + tiles OpenStreetMap. Impressão via `window.print()`.

### 8.3 Sequência de uma avaliação de transmissão

1. Localiza a linha no BRUTO (SQ ou inscrição). Recusa tipologia ≠ Apartamento.  
2. `_preparar_features`: log área, pavimentos, andar/flag, idade (mediana do treino se ano ausente/inválido), tendência (do pool/holdout ou mediana), inscrição relativa.  
3. `calcular_knn_proxy(POOL, params)` — vizinhos causais.  
4. LightGBM → `exp(log)` + intervalo de confiança 80% (quantis empíricos do holdout).  
5. Hedônico OLS → segunda opinião.  
6. SHAP (se disponível) → memória de cálculo (% de contribuição de cada parâmetro).  
7. Até 15 comparáveis: `BallTree` haversine, transações de apartamento nos **36 meses anteriores**, excluindo a SQ avaliada.  
8. Endereço e foto via proxies Google.  
9. HTML com cards de valor, IC, hedônico, tabela de comparáveis e mapa (raio de 500 m).

A inferência **não** aplica Chauvenet, desvio venal ±30% nem corte temporal. Só exige área privativa &gt; 0 para montar `LOG_AREA`.

### 8.4 Avaliação cadastral (sem ITIV)

Usa o cadastro municipal. `VAR_TENDENCIA = 0` (avaliação “hoje”). Compara valor venal com a estimativa de mercado e exibe badge de compatível/defasado. Continua restrita a apartamento.

---

## 9. Avaliação em lote e classificação operacional

### 9.1 Lote

`codigo/gerar_avaliacao_lote_apartamentos.py` (e variantes consolidada / dados tratados) percorre as transmissões aptas e grava Excel com estimativas LightGBM + hedônico.

### 9.2 Status na base bruta

`codigo/gerar_status_avaliacao_raw.py` aplica o modelo à planilha completa (~148 mil linhas, todas as tipologias). Reaproveita estimativas do lote por `SQTRANSMISSAO`. Recalcula o valor declarado atualizado pelo IPCA (a coluna pronta `VLDECLARADOCORRIGIDO` cobre só ~19% das linhas).

**Tolerância operacional:** ±15%, ancorada na meta de COD ≤ 15%.

**Ajuste de fração:** o modelo estima o imóvel **inteiro**. Transmissões parciais usam `VLFRACAOTERRENO` (fallback `VLFRACAOTERRENO` → construção) para escalar a estimativa antes da comparação.

**Regras de status** (decisão 17/07/2026):

| Status | Condição |
|--------|----------|
| Compatível | Razão transação atualizada / estimativa (ajustada pela fração) dentro de ±15% |
| Compatível (transação abaixo do modelo) | Modelo estima **abaixo** da transação e fora de ±15%, mas ainda dentro de 0,5–2,0 — sem risco de arrecadação; **não** vai a auditor |
| Necessidade Avaliação por Auditor | Modelo estima **acima** da transação (indício de subavaliação) e razão em 0,5–2,0 |
| Valor da Transação Suspeito | Razão &lt; 0,5 ou &gt; 2,0 (amplitude &gt; 100%, acima do pior IC 80% da Etapa 5) — provável erro de dado |
| Fora de Escopo do Modelo | Não é apartamento com compra e venda, ou sem estimativa |

A comparação é **sempre** com o valor da transação atualizado, nunca com o venal.

---

## 10. Métricas IAAO (implementação)

Arquivo: `codigo/metricas_iaao_por_decil.py`.

Razão `R = avaliação / preço de venda`:

- **Mediana de R** — nível geral  
- **COD** — `100 × média(|R − mediana|) / mediana`  
- **COD mediano** — versão robusta (mediana dos desvios), menos sensível a vendas simbólicas  
- **PRD** — média das razões / razão ponderada  
- **PRB** — inclinação de `(R − med)/med` sobre `log2` do valor proxy `0,5·preço + 0,5·avaliação/mediana`

Usadas no treino, na Etapa 5, no desafiante e no status em lote.

---

## 11. Integrações externas

| Serviço | Uso | Onde |
|---------|-----|------|
| BCB SGS 433 (IPCA) | Deflação de `VLTRANSACAO` e `VAR_TENDENCIA` | `preparar_base_treino.py`, `src.limpeza` |
| BCB SGS 432 (SELIC) | Feature experimental (não produção) | `desafiante_idade/selic_features.py` |
| Google Geocoding | Endereço reverso no mapa | avaliador `/geocode` |
| Google Street View Static | Foto no popup | avaliador `/streetview` |
| OpenStreetMap / Leaflet (CDN unpkg) | Tiles e mapa | HTML inline |

Não há integração com anúncios imobiliários, corretoras ou bancos em nuvem. O avaliador declara explicitamente: só transações reais do ITIV.

Chave Google: variável de ambiente `GOOGLE_SV_KEY`, com fallback no código-fonte do avaliador. Tratar como risco (ver § 14).

---

## 12. Configuração, artefatos e execução

### 12.1 Resolução de caminhos

Muitos scripts de treino usam path absoluto:

`D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV`

O avaliador é mais portátil: `RAIZ = Path(__file__).parent.parent.parent` (espera a pasta ITIV como avô de `app/`).

### 12.2 Artefatos de produção esperados

```
Modelo_Apartamentos_Aprovado/dados/
├── modelo_lightgbm_apartamentos.txt
├── features_producao.json
├── fill_medians_producao.json
├── Nascimento_Imovel.csv
├── stats_setor_inscricao_treino.parquet
├── vals_inscricao_por_setor.pkl
├── registro_promocao_idade_rel.json
├── avaliacao_holdout_promovido.json
├── legado_v20260714/
└── amostras/
    ├── pool_treino_parametros.parquet
    └── teste_final_previsoes_promovido.parquet
```

### 12.3 Como ligar o avaliador

1. Garantir Python com as bibliotecas do § 4, o pacote `entrega_equipe_20260615` e a pasta `dados/` completa.  
2. Executar `Avaliador Apartamentos.bat` (ou `python avaliador_web_apartamentos.py` a partir de `app/`).  
3. Abrir `http://localhost:8766`.

### 12.4 Como retreinar (resumo)

Ordem típica após nova extração ITIV: Etapa 0 → (opcional 1–3) → 4.1 → 4.2 → 4.4 (inclui Chauvenet por fold) → 5 → lote → status. Features de idade/relativa exigem o fluxo desafiante (ou equivalente) antes de promover.

Reprodutibilidade: semente **42** em splits e modelos.

---

## 13. Padrões arquiteturais

| Padrão | Como aparece |
|--------|----------------|
| Pipeline ETL batch | Scripts numerados Etapas 0–5, execução manual |
| Dual model | LightGBM operacional + OLS normativo |
| Feature store em arquivo | Parquet/JSON/pickle gerados no treino e congelados na inferência |
| Isolamento causal | KNN e Chauvenet recalculados por fold; stats de inscrição só do treino |
| Promoção de candidato | Cópia de artefatos + SHA-256 + arquivo legado |
| Monólito de inferência | Um processo Python, HTML embutido, estado global em memória |

Não há DDD, hexagonal, microserviços, filas, eventos nem MVC clássico.

---

## 14. Segurança e limitações

| Ponto | Detalhe |
|-------|---------|
| Superfície de rede | Bind em localhost; sem TLS, sem autenticação, sem rate limit |
| Dados fiscais | Base ITIV completa em RAM no processo do avaliador |
| Chave Google | Fallback hardcoded no avaliador — deve ser extraída para segredo de ambiente |
| Erros na UI | Traceback (até 1500 caracteres) pode ir para o HTML |
| Proxies `/geocode` e `/streetview` | Encaminham coordenadas ao Google; uso previsto é local |
| Paths absolutos | Acoplam treino à estação da equipe; dificultam CI/portabilidade |
| Pacote legado não versionado aqui | `entrega_equipe_20260615` é dependência opaca de supply chain |
| Sem `requirements.txt` | Versões de LightGBM/pandas não estão pinadas no Git |

Mitigações conscientes: localhost; escopo Apartamento; texto de “subsídio técnico”; Chauvenet só no treino; IC 80% empírico no holdout.

---

## 15. Roadmap de regimes por tipologia

Documentado em `Documentacao_e_Relatorios/ESPECIFICACAO_REGIMES_POR_TIPOLOGIA.md` (rascunho). O avaliador atual **recusa** tipologias que não sejam Apartamento.

| Código | Quando | Estado |
|--------|--------|--------|
| `MERCADO_ML` | Apartamento no envelope validado | **Implementado** |
| `PGV_ASSISTIDO` | Casa, loja, sala — venal/PGV como referência | Especificado, não no avaliador |
| `AVALIACAO_INDIVIDUAL` | Terreno, atípicos, demais | Especificado; status de lote já sinaliza fora de escopo / suspeito |

Apartamento ≈ 80% da base limpa (97.990 de 121.932). Demais tipos não têm densidade para repetir Etapas 4–5 com as mesmas metas IAAO.

---

## 16. Mapa de módulos

| Módulo | Caminho | Responsabilidade |
|--------|---------|------------------|
| Avaliador | `Modelo_Apartamentos_Aprovado/app/avaliador_web_apartamentos.py` | Inferência + UI |
| Biblioteca ML | `.../codigo/apartamentos_lib.py` | Features base, KNN, hedônico, métricas |
| Idade | `.../codigo/idade_features.py` | Merge nascimento, flags, imputação explícita |
| Inscrição relativa | `.../codigo/inscricao_relativa.py` | Stats de treino + anexação na inferência |
| Chauvenet | `.../codigo/saneamento_chauvenet_iterativo.py` | Outliers só no treino |
| IAAO | `.../codigo/metricas_iaao_por_decil.py` | COD, PRD, PRB |
| Base limpa | `.../codigo/construir_base_limpa.py` | Etapa 0 |
| Preparação treino | `.../codigo/preparar_base_treino.py` | Etapa 4.1 |
| Engenharia | `.../codigo/engenharia_parametros_treino.py` | Etapa 4.2 |
| Treino | `.../codigo/treinar_modelo_apartamentos.py` | Etapa 4.4 |
| Validação | `.../codigo/etapa5_validacao_normativa.py` | Etapa 5 |
| Status lote | `.../codigo/gerar_status_avaliacao_raw.py` | Classificação operacional |
| Desafiante | `desafiante_idade/pipeline_idade_apartamentos.py` | Experimento idade |
| Promoção | `desafiante_idade/promover_candidato_producao.py` | Candidato → produção |
| Conformidade | `Documentacao_e_Relatorios/PROJETO_Conformidade_Normas_Avaliacao.md` | Requisitos normativos |
| Lista de parâmetros | `Modelo_Apartamentos_Aprovado/decisoes_e_aprovacao/Lista_Final_Parametros_Apartamentos.md` | Decisão de features (09/07/2026) |

---

## 17. Resumo do fluxo ponta a ponta

```
Extração Excel ITIV
    → filtros de mercado (base limpa)
    → recorte apartamentos + plausibilidade + IPCA (amostra de treino)
    → log-área, localização, andar
    → Chauvenet e KNN só no treino
    → LightGBM (log valor) + OLS hedônico
    → holdout IAAO / NBR
    → promoção de artefatos
    → avaliador local (consulta unitária) e Excel de status (lote)
    → auditor decide autuação
```

A solução é um **sistema de ciência de dados com governança normativa**, empacotado para uso fiscal em workstation. O contrato de qualidade (COD/PRD/PRB, Chauvenet só no treino, dual model, KNN causal) é tão parte da arquitetura quanto o servidor na porta 8766.
