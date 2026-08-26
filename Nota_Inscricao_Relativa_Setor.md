# Inscrição relativa no setor (crítica Gabriel — ritmo de cadastro)

- `LOG_INSCRICAO_REL` = log(inscrição) − mediana do setor (treino)
- `RANK_INSCRICAO_SETOR` = percentil da inscrição dentro do setor (0=antigo no pedaço, 1=novo)

Estatísticas de setor calculadas **só no pool de treino** (sem vazamento do holdout). 104 setores; n mediano ≈ 144.

| Modelo | COD mediano | Δ vs baseline | COD antigos (&lt;300k) | Δ antigos |
|---|---:|---:|---:|---:|
| idade_mais_rel | **6,383%** | +0,147 | 9,68% | +1,14 |
| idade_abs_rel | 6,392% | +0,138 | **9,58%** | +1,24 |
| idade_mais_abs | 6,434% | +0,096 | 9,78% | +1,04 |
| so_inscricao_abs | 6,467% | +0,063 | 10,28% | +0,54 |
| baseline | 6,530% | 0 | 10,82% | 0 |
| so_inscricao_rel | 6,534% | −0,004 | 9,99% | +0,83 |
| abs_mais_rel | 6,559% | −0,029 | 9,97% | +0,85 |

## Interpretação

- **Só relativa sem idade** não bate a inscrição absoluta no global (6,53% ≈ baseline), mas **ajuda mais os antigos** (10,82% → 9,99%).
- Com **idade**, trocar absoluto → relativo **melhora o global** (6,43% → **6,38%**) e os antigos (9,78% → 9,68%).
- **Idade + absoluto + relativo** é o melhor nos antigos (**9,58%**), quase empatado no global com idade+relativo.
- O número absoluto ainda carrega “época da cidade”; o relativo responde à crítica do ritmo e acrescenta sinal **local**.
- Correlações: absoluto×relativo ≈ 0,81; idade×rank setor ≈ −0,62 (coerente, não idêntico).

## Recomendação prática

Candidato forte: **idade + inscrição relativa no setor** (ou idade + abs + rel se o foco for equidade nos antigos).  
Absoluto sozinho continua útil como fallback simples; relativo é o refinamento alinhado ao ponto do Gabriel.

Arquivos: `desafiante_idade/saida/comparativo_inscricao_relativa_setor.json`, `preds_inscricao_relativa_setor.csv`.
