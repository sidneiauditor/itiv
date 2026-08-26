# A/B inscricao × idade × ambas (proposta Gabriel Ramos)

Proxy de idade via `LOG_INSCRICAO = log1p(CDINSCRICAOIMOB)` (cobertura ~100%).
Idade declarada: `IDADE_NA_TRANSACAO_IMP, FLAG_ANO_AUSENTE, FLAG_ANO_INVALIDO` (Nascimento Imovel).

| Modelo | COD mediano | Δ vs baseline (pp) | COD | PRD | Importância foco |
|---|---:|---:|---:|---:|---|
| idade_mais_inscricao | 6.434% | +0.096 | 9.19% | 1.0161 | IDADE_NA_TRANSACAO_IMP=4447, FLAG_ANO_AUSENTE=172, FLAG_ANO_INVALIDO=97, LOG_INSCRICAO=5244 |
| so_idade | 6.438% | +0.092 | 9.28% | 1.0162 | IDADE_NA_TRANSACAO_IMP=5855, FLAG_ANO_AUSENTE=229, FLAG_ANO_INVALIDO=164 |
| so_inscricao | 6.467% | +0.063 | 9.27% | 1.0157 | LOG_INSCRICAO=6674 |
| baseline_aprovado | 6.530% | +0.000 | 9.60% | 1.0175 | — |

**Melhor modelo:** `idade_mais_inscricao` (COD mediano = 6.434%).

## Por faixa de inscricao (COD mediano)

| Modelo | <300k | 300-900k | >900k | com ano | sem ano |
|---|---:|---:|---:|---:|---:|
| idade_mais_inscricao | 9.78% | 8.37% | 3.98% | 6.31% | 8.20% |
| so_idade | 10.39% | 8.28% | 3.95% | 6.31% | 8.27% |
| so_inscricao | 10.28% | 8.50% | 3.93% | 6.31% | 8.48% |
| baseline_aprovado | 10.82% | 8.64% | 4.00% | 6.33% | 8.96% |

## Interpretação

- Se **so_inscricao** ≈ **so_idade**: a sacada do Gabriel (inscrição como idade) funciona na prática e cobre quem não tem ano de construção.
- Se **idade_mais_inscricao** ganha: há sinal complementar (ritmo de cadastro ≠ idade física).
- Se **so_idade** ganha e inscrição pouco ajuda: priorizar nascimento; inscrição fica como fallback.

Arquivos: `comparativo_inscricao_vs_idade.json`, `preds_inscricao_vs_idade.csv`.
