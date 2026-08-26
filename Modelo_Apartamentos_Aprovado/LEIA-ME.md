# Modelo de Apartamentos (ITIV) — produção com idade + inscrição relativa

**Promovido em:** 2026-08-26  
**Candidato:** `idade_mais_rel` (pacote `Modelo_Apartamentos_Candidato_Idade_20260811`)  
**Substitui:** LightGBM de 14/07/2026 (arquivado em `dados/legado_v20260714/`)

## O que mudou

O modelo em produção passa a usar, além dos 9 parâmetros originais:

- **idade** na data da transação (`IDADE_NA_TRANSACAO_IMP` + flags de ano ausente/inválido);
- **inscrição relativa no setor** (`LOG_INSCRICAO_REL`, `RANK_INSCRICAO_SETOR`).

## Holdout (candidato promovido)

| Métrica | Valor |
|---|---:|
| COD mediano | 6.383% |
| COD | 9.231% |
| PRD | 1.0157 |
| PRB | -0.0084 |

## Avaliador HTML

Execute `Avaliador Apartamentos.bat` (ou `app/avaliador_web_apartamentos.py`).  
Abra http://localhost:8766

## Artefatos de promoção

- `dados/registro_promocao_idade_rel.json`
- `dados/features_producao.json`
- `dados/fill_medians_producao.json`
- `dados/Nascimento_Imovel.csv`
- `dados/stats_setor_inscricao_treino.parquet`
- `dados/vals_inscricao_por_setor.pkl`
