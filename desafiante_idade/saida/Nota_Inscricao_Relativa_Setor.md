# Inscricao relativa no setor (critica Gabriel — ritmo de cadastro)

- `LOG_INSCRICAO_REL` = log(inscricao) − mediana do setor (treino)
- `RANK_INSCRICAO_SETOR` = percentil da inscricao dentro do setor (0=antigo, 1=novo)

| Modelo | COD mediano | Δ vs baseline | COD antigos (<300k) | Δ antigos |
|---|---:|---:|---:|---:|
| idade_mais_rel | 6.383% | +0.147 | 9.68% | +1.14 |
| idade_abs_rel | 6.392% | +0.138 | 9.58% | +1.24 |
| idade_mais_abs | 6.434% | +0.096 | 9.78% | +1.04 |
| so_inscricao_abs | 6.467% | +0.063 | 10.28% | +0.54 |
| baseline | 6.530% | +0.000 | 10.82% | +0.00 |
| so_inscricao_rel | 6.534% | -0.004 | 9.99% | +0.83 |
| abs_mais_rel | 6.559% | -0.029 | 9.97% | +0.85 |

**Melhor global:** `idade_mais_rel`.

## Interpretação

- Se **so_inscricao_rel** ≈ ou > **so_inscricao_abs**: a forma relativa responde à crítica do ritmo sem perder sinal.
- Se absoluto ganha: o número bruto ainda carrega informação de época da cidade (não só posição local).
- Se **idade_abs_rel** ganha pouco sobre **idade_mais_abs**: relativo é refinamento, não troca de estratégia.

Arquivos: `comparativo_inscricao_relativa_setor.json`, `preds_inscricao_relativa_setor.csv`.
