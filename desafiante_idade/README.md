# Modelo desafiante — idade do imóvel (apartamentos ITIV)

Pipeline experimental que **não substitui** o modelo aprovado em
`Modelo_Apartamentos_Aprovado/`.

## Como rodar

```bat
cd "D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\desafiante_idade"
set PYTHONUNBUFFERED=1
python -u pipeline_idade_apartamentos.py
```

## Saídas (`saida/`)

| Arquivo | Conteúdo |
|---|---|
| `diagnostico_idade_status.json` | Compatível × inscrição × idade (confirmação e-mail David) |
| `diagnostico_por_*.csv` | Tabelas por faixa |
| `grafico_*.png` | Gráficos do diagnóstico |
| `pool_treino_com_idade.parquet` / `teste_final_com_idade.parquet` | Features com idade |
| `teste_final_previsoes_desafiante.parquet` | Previsões baseline vs desafiante |
| `modelo_lightgbm_apartamentos_com_idade.txt` | LightGBM desafiante |
| `comparativo_baseline_desafiante.json` | Métricas CV/holdout/IAAO estratificado |
| `Nota_Tecnica_Idade_Modelo_Apartamentos.md` | Adendo ao RIF 114 |

Cópia da nota também em `ITIV/Nota_Tecnica_Idade_Modelo_Apartamentos.md`.
