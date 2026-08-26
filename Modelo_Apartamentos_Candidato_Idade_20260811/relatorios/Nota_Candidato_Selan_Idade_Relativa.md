# Nota para decisão Selan — candidato idade + inscrição relativa

**Data:** 11/08/2026  
**Status:** experimental — **não** substitui o modelo aprovado (14/07/2026) até decisão formal.  
**Candidato recomendado:** `idade_mais_rel` (aprovado + idade + inscrição relativa no setor).  
**Alternativa (melhor nos antigos nos testes anteriores):** `idade_abs_rel`.

---

## 1. O que foi feito

1. Confirmou-se o candidato **idade + inscrição relativa** (`LOG_INSCRICAO_REL`, `RANK_INSCRICAO_SETOR`).
2. Gravou-se o artefato LightGBM do candidato (mesmos hiperparâmetros do aprovado).
3. Reprocessou-se o status **Compatível** no **holdout** com a regra operacional (±15%; suspeito fora de 0,5–2,0).
4. Cruzou-se com a planilha de status (mesmo `VALOR_TX` usado no diagnóstico do David).

SELIC permanece fora (teste anterior sem ganho).

---

## 2. Holdout — métricas IAAO

| Modelo | COD mediano | COD | PRD |
|---|---:|---:|---:|
| baseline | 6.530% | 9.603% | 1.0175 |
| idade_mais_rel | 6.383% | 9.231% | 1.0157 |
| idade_abs_rel | 6.392% | 9.187% | 1.0160 |

---

## 3. Holdout — % Compatível (valor deflacionado da amostra)

| Modelo | % Compatível | % dos Compatível com inscrição >900k |
|---|---:|---:|
| baseline | 87.9% | 44.0% |
| idade_mais_rel | 88.8% | 43.5% |
| idade_abs_rel | 88.9% | 43.4% |

### Por inscrição — candidato idade_mais_rel (holdout)
| Faixa | N | % Compatível | % Auditor |
|---|---:|---:|---:|
| <300k | 1,082 | 81.2% | 18.7% |
| 300-900k | 4,362 | 86.5% | 13.3% |
| >900k | 3,832 | 93.6% | 6.4% |

### Por inscrição — baseline (holdout)
| Faixa | N | % Compatível | % Auditor |
|---|---:|---:|---:|
| <300k | 1,082 | 74.6% | 25.1% |
| 300-900k | 4,362 | 86.3% | 13.5% |
| >900k | 3,832 | 93.5% | 6.5% |

---

## 4. Cruzamento com planilha de status (VALOR_TX operacional)

N = 9,278 (holdout ∩ status com estimativa).

### Baseline reclassificado
| Faixa | N | % Compatível | % Auditor |
|---|---:|---:|---:|
| <300k | 1,082 | 74.4% | 25.2% |
| 300-900k | 4,364 | 86.2% | 13.6% |
| >900k | 3,832 | 93.4% | 6.6% |

### idade_mais_rel
| Faixa | N | % Compatível | % Auditor |
|---|---:|---:|---:|
| <300k | 1,082 | 81.0% | 18.9% |
| 300-900k | 4,364 | 86.3% | 13.5% |
| >900k | 3,832 | 93.5% | 6.5% |

### idade_abs_rel
| Faixa | N | % Compatível | % Auditor |
|---|---:|---:|---:|
| <300k | 1,082 | 81.0% | 18.9% |
| 300-900k | 4,364 | 86.4% | 13.4% |
| >900k | 3,832 | 93.4% | 6.6% |

**Concentração David (% Compatível que tem inscrição >900k):**  
baseline 43.94% · idade_mais_rel 43.56% · idade_abs_rel 43.52%

---

## 5. Recomendação

| Pergunta | Sugestão |
|---|---|
| Promover agora a produção? | **Não automaticamente** — falta Etapa 5 normativa + manifesto + lote completo |
| Qual candidato? | **idade_mais_rel** (melhor COD global) |
| Prioridade = antigos? | Avaliar também **idade_abs_rel** |
| Modelo aprovado? | Continua congelado até decisão formal |

### Checklist promoção
- [ ] Revisar esta nota e `desafiante_idade/saida/grafico_compativel_candidato_por_inscricao.png`
- [ ] Etapa 5 normativa no candidato
- [ ] Regenerar lote + planilha de status completa
- [ ] Manifesto SHA-256
- [ ] Registro formal de aprovação

---

## 6. Artefatos

| Arquivo | Conteúdo |
|---|---|
| `modelo_lightgbm_candidato_idade_rel.txt` | LightGBM candidato |
| `stats_setor_inscricao_treino.parquet` | Medianas por setor |
| `vals_inscricao_por_setor.pkl` | Distribuições para rank |
| `comparativo_compativel_candidato_selan.json` | Números completos |
| `cruzamento_status_candidato_holdout.parquet` | Status reprocessado |
| `grafico_compativel_candidato_por_inscricao.png` | Comparativo visual |

---

*Coordenadoria de Inteligência Fiscal — SEFAZ Salvador*
