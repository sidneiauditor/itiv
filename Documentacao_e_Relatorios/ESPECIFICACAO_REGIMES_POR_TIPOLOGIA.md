# Especificação — Regimes de Avaliação por Tipologia (ITIV)

**Coordenadoria de Inteligência Fiscal — SEFAZ Salvador**  
**Data:** 20/07/2026  
**Status:** rascunho para alinhamento (equipe + Dilson) antes da conversa com a direção  
**Complementa:** modelo de apartamentos aprovado em 14/07/2026 (`Modelo_Apartamentos_Aprovado/`)

---

## 1. O que muda (e o que não muda)

| | Antes (entrega atual) | Depois (esta especificação) |
|---|---|---|
| Apartamentos na faixa validada | Modelo ML aprovado | **Sem mudança** — permanece o modelo 14/07 |
| Casa, loja, sala, terreno, etc. | Sem regra escrita / avaliador novo recusa | **Regra explícita por tipologia** (matriz abaixo) |
| Aptos de alto valor / atípicos | Mesmo modelo, sem flag formal | **Regime assistido** + flag de avaliação individual |
| Dossiê Selan | Só aptos | Aptos **+ este anexo** (cobertura 100% dos tipos) |

**Não muda agora:** treinar modelo ML próprio de casa/terreno/loja. Isso fica na Fase 2, só se o diagnóstico de amostra fechar.

---

## 2. Princípio

Para **todo** imóvel consultado, o sistema deve responder com um dos três regimes e **registrar qual usou**:

| Código | Nome | Quando |
|--------|------|--------|
| `MERCADO_ML` | Estimativa de mercado (modelo) | Tipologia e faixa com modelo validado |
| `PGV_ASSISTIDO` | Referência pela PGV / valor venal | Sem modelo de mercado defensável; auditor decide |
| `AVALIACAO_INDIVIDUAL` | Encaminhar a laudo | Atípico, amostra insuficiente ou tipo fora do automático |

Fundamento: IBAPE 7.3.2 (modelo por segmento quando possível), 7.6.2 (amostra única com variável de segmento se faltar massa), 7.1.3(a) (atípicos → avaliação individual).

**PGV**, nesta especificação = valor venal cadastral vigente (`VLVENALCADASTRO` / planta genérica de valores da Prefeitura), até a equipe confirmar outro artefato com o Dilson.

---

## 3. Matriz operacional (decisão a validar)

| Tipologia (`DSSUBUNIDADE`) | Regime V1 | Fonte do valor | Sinalização automática ITIV? |
|----------------------------|-----------|----------------|------------------------------|
| Apartamento (dentro do envelope da amostra) | `MERCADO_ML` | LightGBM + hedônico âncora | Sim (confiança 90%, decisão D5) |
| Apartamento atípico / alto valor (*) | `AVALIACAO_INDIVIDUAL` (ou assistido com alerta) | Estimativa ML **com flag** + PGV como apoio | Não autuar só pelo ponto central |
| Casa | `PGV_ASSISTIDO` | PGV/venal | Não — auditor decide |
| Loja, Sala, Sobre-loja | `PGV_ASSISTIDO` | PGV/venal | Não — auditor decide |
| Terreno | `AVALIACAO_INDIVIDUAL` | PGV/venal ou laudo | Não |
| Garagem, Box, Galpão, Outros, Prédio, etc. | `AVALIACAO_INDIVIDUAL` | Laudo / análise | Não |

(*) Critérios sugeridos de “atípico / alto valor” (escolher um e registrar):

- **Opção A:** valor ou área fora do p5–p95 da amostra de treino do setor; ou  
- **Opção B:** valor de transação / venal fora do suporte visto no treino; ou  
- **Opção C (provisória):** VLTRANSACAO > R$ 1.000.000 (há ~2.664 aptos plausíveis nessa faixa; > R$ 2 mi só ~414).

Recomendação técnica: **Opção A** (envelope estatístico) + faixa de confiança mais larga; Opção C só como limiar provisório até medir.

---

## 4. Volumes que justificam a matriz (base limpa 121.932)

| Tipologia | N limpa | Após VLITIV>0 e desvio venal ≤±30% |
|-----------|--------:|----------------------------------:|
| Apartamento | 97.990 | 46.447 |
| Casa | 9.668 | 3.050 |
| Sala | 7.138 | 1.244 |
| Loja | 2.611 | 734 |
| Terreno | 1.350 | 292 |

Apartamento = ~80% da base limpa. Demais tipologias não têm, hoje, a mesma densidade para repetir o pipeline das Etapas 4–5 com as mesmas metas IAAO.

---

## 5. Como alterar o sistema (passos técnicos)

### 5.1 Documento / dossiê (fazer agora — sem código)

1. Validar esta matriz com Dilson (definição de PGV + limiar de atípico).  
2. Anexar este arquivo (ou versão Word) ao pacote Selan.  
3. Atualizar a frase de “pendência” do resumo executivo: de “projeto futuro” para “especificação V1 anexa; ML próprio em fase posterior”.

### 5.2 Avaliador web novo (`Modelo_Apartamentos_Aprovado/app/avaliador_web_apartamentos.py`)

Hoje: se não for Apartamento → mensagem de erro e para.

Alterar para um **roteador**:

```text
se tipologia == Apartamento e não atípico:
    regime = MERCADO_ML  → fluxo atual do modelo
senao se tipologia in {Casa, Loja, Sala, ...}:
    regime = PGV_ASSISTIDO → mostrar venal + texto "sem modelo de mercado; referência PGV"
senao:
    regime = AVALIACAO_INDIVIDUAL → mostrar venal (se houver) + "encaminhar avaliação individual"
```

Sempre gravar/exibir o código do regime na tela e no export.

### 5.3 Avaliador legado (`entrega_equipe_20260615`)

Já tinha escopo V1 no `LEIA-ME.txt` (apto automático / casa-comercial assistido / terreno fora). Alinhar a documentação e a UI à matriz da seção 3 para não haver duas regras diferentes.

### 5.4 O que **não** alterar no pipeline de treino

- Não misturar Casa/Loja/Terreno no `preparar_base_treino.py` / LightGBM de apartamentos.  
- Não relaxar metas IAAO do apto para “caber” outros tipos.  
- Filtros de treino (±30% venal, Chauvenet) continuam só na amostra; inferência cobre o universo com flag (IBAPE 7.6.7 / 7.9.1).

---

## 6. Critério para promover tipologia a modelo próprio (Fase 2)

Só abrir projeto de modelo ML para Casa / Comercial / Terreno se, após o mesmo saneamento usado no apto:

1. Amostra holdout suficiente;  
2. COD na faixa IAAO do tipo (residencial ≤15%; comercial ≤20%; terreno ≤25%);  
3. PRD/PRB dentro da meta;  
4. Decisão formal da equipe registrada no `REGISTRO_ETAPAS_APROVACAO`.

Até lá, o regime permanece `PGV_ASSISTIDO` ou `AVALIACAO_INDIVIDUAL`.

---

## 7. Checklist de alinhamento (Dilson → Ulysses)

- [ ] Confirmar: PGV = valor venal cadastral?  
- [ ] Confirmar limiar de apartamento atípico/alto valor (A, B ou C).  
- [ ] Confirmar matriz da seção 3 (Casa/Loja = assistido; Terreno = individual).  
- [ ] Confirmar: este anexo entra no pacote Selan nesta entrega.  
- [ ] Definir prazo do diagnóstico Fase 2 (contagens + COD venal×venda por tipo).

---

## 8. Texto curto para a direção (Ulysses)

> O modelo ML aprovado cobre apartamentos (~80% das transações), com validação normativa completa. Para os demais tipos — e para apartamentos fora da faixa confiável — o sistema passa a ter especificação explícita: referência pela PGV/valor venal em regime assistido, ou encaminhamento a avaliação individual, conforme a tipologia. Assim há regra para 100% dos imóveis, sem forçar um modelo de mercado onde a amostra ainda não sustenta as metas técnicas. A promoção de casa/loja/terreno a modelo próprio fica condicionada a diagnóstico e metas IAAO por tipo.

---

## 9. Decisões em aberto (preencher na reunião)

| # | Pergunta | Decisão | Data |
|---|----------|---------|------|
| 1 | Definição de PGV | | |
| 2 | Limiar apto atípico | | |
| 3 | Casa/Loja: `PGV_ASSISTIDO` ok? | | |
| 4 | Terreno: individual ok? | | |
| 5 | Anexo no Selan nesta entrega? | | |

**Aprovação da equipe:** ( ) Aprovado  ( ) Ajustar — _____________
