# Teste KNN geografico × KNN com idade/inscricao

O `KNN_PROXY` aprovado busca os k vizinhos **só por coordenadas** e usa a média do log(R$/m²).
Aqui testamos vizinhos que também sejam parecidos em **inscrição** ou **idade**.

| Modelo | COD mediano | Δ vs baseline | COD antigos (<300k) | Δ antigos |
|---|---:|---:|---:|---:|
| idade_insc_knn_insc | 6.421% | +0.109 | 9.85% | +0.97 |
| idade_insc_knn_geo | 6.434% | +0.096 | 9.78% | +1.04 |
| idade_insc_knn_geo_mais_insc | 6.523% | +0.007 | 10.23% | +0.59 |
| baseline_knn_geo | 6.530% | +0.000 | 10.82% | +0.00 |
| baseline_knn_geo_mais_insc | 6.634% | -0.104 | 10.56% | +0.26 |
| baseline_knn_insc | 6.638% | -0.108 | 10.24% | +0.58 |
| baseline_knn_idade | 6.715% | -0.185 | 10.81% | +0.01 |

**Melhor global:** `idade_insc_knn_insc` (quase empatado com idade+inscrição + KNN geo).

## Interpretação (resultado)

- Trocar o KNN geográfico pelo KNN com inscrição **sozinho** (sem idade/inscrição no LightGBM) **piora** o global, embora ajude um pouco os antigos (10,82% → 10,24%).
- Com **idade + inscrição já no modelo**, trocar KNN_GEO → KNN_INSC empata/melhora de leve no global (6,43% → 6,42%), mas **não melhora os antigos** vs o candidato anterior (9,85% vs 9,78%).
- Usar **os dois KNNs juntos** piora (redundância; correlação KNN_GEO×KNN_INSC ≈ 0,97).
- Conclusão: o ganho nos antigos vem sobretudo de **colocar idade/inscrição como features**, não de redesenhar o KNN. O KNN “com idade” é ideia boa, mas neste desenho é **quase redundante**.

Arquivos: `desafiante_idade/saida/comparativo_knn_idade.json`, `preds_knn_idade.csv`.
