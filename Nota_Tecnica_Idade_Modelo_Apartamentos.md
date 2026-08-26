# Nota técnica — Idade do imóvel no modelo de apartamentos (ITIV)

**Adendo analítico ao Relatório de Inteligência Fiscal 114/2026**  
**Data:** 10/08/2026  
**Referência:** e-mails Marcos (03/08) e David (04/08/2026) sobre Compatível × inscrição > 900.000  
**Fonte de idade:** `Nascimento Imovel.csv` (`CDINSCRICAOIMOB`; `AACONSTRUCAO`)

---

## 1. Achado do David (confirmado)

Entre as avaliações classificadas como **Compatível** (inclui “Compatível — valor da transação abaixo do estimado”):

| Indicador | Valor |
|---|---|
| N Compatível | 79,344 |
| Compatível com inscrição > 900.000 | 35,296 (**44.48%**) |
| % dos Não Compatíveis com inscrição > 900k | 18.81% |
| Idade mediana (Compatível) | 12.0 |
| Idade mediana (Não Compatível*) | 25.0 |
| Cobertura de idade na base de status | 76.85% |

\*Exceto “Fora de Escopo”.

A observação de David (~48% dos Compatível com inscrição > 900k) está **alinhada** aos dados. Inscrição alta correlaciona com estoque **novo / pouco depreciado** (mediana de ano de construção ~2021 na faixa >900k). O modelo aprovado **não usa idade** como feature; localização, área e KNN absorvem parcialmente o efeito de vintage, com aderência desigual.

### 1.1 % Compatível e IAAO por faixa de inscrição (modelo aprovado × status)

| Faixa | N | % Compatível | COD mediano | PRD | Idade mediana |
|---|---:|---:|---:|---:|---:|
| <300k | 14383 | 50.95 | 14.9578 | 1.0116 | 49.0 |
| 300-900k | 57508 | 63.85 | 13.028 | 1.0387 | 20.0 |
| >900k | 42379 | 83.29 | 8.2855 | 1.0054 | 1.0 |

### 1.2 % Compatível por faixa etária

| Faixa | N | % Compatível | COD mediano | PRD | Idade mediana |
|---|---:|---:|---:|---:|---:|
| 0-5 | 23742 | 78.88 | 9.3851 | 1.0259 | 1.0 |
| 6-15 | 21745 | 69.91 | 11.1776 | 1.0584 | 10.0 |
| 16-30 | 15532 | 60.35 | 12.9978 | 1.03 | 21.0 |
| 31-50 | 21534 | 56.3 | 14.8239 | 1.0019 | 40.0 |
| 50+ | 5259 | 47.88 | 14.5635 | 1.0182 | 55.0 |
| (sem idade) | 26458 | 80.88 | 8.8403 | 1.0007 | None |

Gráficos: `desafiante_idade/saida/grafico_compativel_por_faixa.png`, `grafico_cod_por_inscricao.png`.

---

## 2. Engenharia proposta (e implementada no desafiante)

- Join por `CDINSCRICAOIMOB` com `Nascimento Imovel.csv`
- `AACONSTRUCAO` higienizado: apenas anos em `[1500, ano_da_transação]`
- `IDADE_NA_TRANSACAO = ano_transação − AACONSTRUCAO`
- `FLAG_ANO_AUSENTE`, `FLAG_ANO_INVALIDO`
- Para o LightGBM: `IDADE_NA_TRANSACAO_IMP` = idade com mediana imputada **somente** onde a flag marca ausência (transparência via flags)
- **Não** usar o número de inscrição como proxy definitivo de idade (apenas corte diagnóstico)

Arquivos: `pool_treino_com_idade.parquet`, `teste_final_com_idade.parquet`.

---

## 3. Modelo desafiante vs baseline (mesmo hiperparâmetro do aprovado)

Hiperparâmetros congelados do LightGBM aprovado: `{'learning_rate': 0.05, 'min_child_samples': 20, 'n_estimators': 800, 'num_leaves': 63, 'random_state': 42, 'verbosity': -1}`.  
CV externa k=5 (pragmático; protocolo completo do manifesto usa k=10).

### Holdout (teste final)

| Modelo | Razão mediana | COD | COD mediano | PRD | PRB |
|---|---:|---:|---:|---:|---:|
| Baseline (sem idade) | 0.9986 | 9.57 | 6.59 | 1.0169 | -0.0088 |
| Desafiante (+ idade) | 0.9997 | 9.27 | 6.50 | 1.0160 | -0.0090 |
| Δ COD mediano (base − desaf.) | | | **0.092** | | |

### Holdout estratificado por inscrição — COD mediano

| Faixa | Baseline | Desafiante |
|---|---:|---:|
| <300k | 10.941567331562903 | 10.428955612660353 |
| 300-900k | 8.557011208195979 | 8.29109613889454 |
| >900k | 4.067316456743631 | 4.029140293504247 |

### Importância (ganho) — top features do desafiante

- `LOG_AREA`: 8850
- `VAR_TENDENCIA`: 8323
- `KNN_PROXY`: 7192
- `IDADE_NA_TRANSACAO_IMP`: 5545
- `VLCOORDGEOY`: 4997
- `VLCOORDGEOX`: 4757
- `NUPAVIMENTOS`: 4086
- `CDSETORFISCAL`: 3332
- `ANDAR_UNIDADE`: 2192
- `FLAG_ANO_AUSENTE`: 232
- `FLAG_ANO_INVALIDO`: 94
- `FLAG_ANDAR_AUSENTE`: 0


Artefato: `D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\desafiante_idade\saida\modelo_lightgbm_apartamentos_com_idade.txt`  
Comparativo completo: `desafiante_idade/saida/comparativo_baseline_desafiante.json`

---

## 4. Governança e recomendação

- O **modelo aprovado permanece congelado** em `Modelo_Apartamentos_Aprovado/`.
- O desafiante é linha experimental sob `desafiante_idade/`.
- Critério de sucesso do plano: melhorar COD/PRD no estoque antigo sem degradar o novo; reduzir assimetria da taxa Compatível entre faixas.

**Recomendação:** promover o modelo desafiante a *candidato* a substituição do aprovado, após revisão SELAN (holdout + resíduos espaciais + reprocessamento do status Compatível). O modelo aprovado permanece em produção até essa decisão.

### Próximos passos sugeridos à equipe

1. Reprocessar status Compatível com o desafiante e repetir a tabela do §1.
2. Se promover: dossiê SELAN (Etapa 5 normativa) + manifesto SHA-256 novo.
3. Testar interação idade × `CDSETORFISCAL` se o ganho no estoque antigo for insuficiente.
4. Estender nascimento a salas (prioridade do relatório de 04/08) após fechar apartamentos.

---

*Gerado automaticamente por `desafiante_idade/pipeline_idade_apartamentos.py`.*
