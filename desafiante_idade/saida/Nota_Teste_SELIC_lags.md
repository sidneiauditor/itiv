# Teste SELIC — D0 / M3 / M6 (proposta Gabriel Ramos)

Série: BCB SGS **432** (Selic meta % a.a.).

| Modelo | COD mediano | Δ vs baseline (pp) | COD | PRD | Imp. SELIC |
|---|---:|---:|---:|---:|---|
| idade_desafiante | 6.438% | +0.092 | 9.28% | 1.0162 | — |
| idade_mais_SELIC_3lags | 6.438% | +0.092 | 9.31% | 1.0163 | SELIC_D0=2029, SELIC_M3=1461, SELIC_M6=1730 |
| idade_mais_SELIC_D0 | 6.501% | +0.029 | 9.29% | 1.0159 | SELIC_D0=2626 |
| idade_mais_SELIC_M3 | 6.505% | +0.025 | 9.30% | 1.0165 | SELIC_M3=2404 |
| idade_mais_SELIC_M6 | 6.514% | +0.016 | 9.32% | 1.0162 | SELIC_M6=2425 |
| baseline_aprovado | 6.530% | +0.000 | 9.60% | 1.0175 | — |
| baseline_mais_SELIC_M6 | 6.587% | -0.058 | 9.64% | 1.0171 | SELIC_M6=2517 |
| baseline_mais_SELIC_3lags | 6.596% | -0.066 | 9.63% | 1.0173 | SELIC_D0=2146, SELIC_M3=1628, SELIC_M6=1764 |
| baseline_mais_SELIC_D0 | 6.636% | -0.106 | 9.61% | 1.0174 | SELIC_D0=2749 |
| baseline_mais_SELIC_M3 | 6.660% | -0.130 | 9.66% | 1.0175 | SELIC_M3=2630 |

**Melhor lag isolado (sobre o baseline):** `baseline_mais_SELIC_M6` (Δ COD mediano = -0.058 pp) — ou seja, o menos pior, ainda assim pior que o baseline.

**Melhor modelo geral neste teste:** `idade_desafiante` (COD mediano = 6.438%).

## Interpretação (para a equipe)

- No baseline **sem idade**, nenhuma coluna SELIC melhorou o holdout: D0/M3/M6 e as três juntas **pioraram** levemente o COD mediano (provável sobreposição com `VAR_TENDENCIA`, que já captura o ciclo no tempo).
- Entre os lags isolados no baseline, **M6 foi o menos pior** — não confirma ganho pelo atraso de 6 meses.
- Com **idade**, o melhor continua sendo o desafiante só com idade; idade+3 lags SELIC **empata**, sem ganho material.
- Conclusão prática: **priorizar idade/inscrição**; SELIC fica como experimento secundário (talvez via variação ΔSELIC, não só o nível da taxa).

Arquivos: `desafiante_idade/saida/comparativo_selic_lags.json`, `selic_sgs432.csv`.
