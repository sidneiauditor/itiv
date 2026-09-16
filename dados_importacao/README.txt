Coloque neste diretório os arquivos da equipe (não versionados).

Layout esperado após organizar:

  dados_importacao/pronto/
    itiv_bruto.parquet
    tabela_modelagem.parquet
    ipca.csv
    Imoveis Salvador.parquet
    Nascimento_Imovel.csv
    pool_treino_parametros.parquet
    stats_setor_inscricao_treino.parquet
    vals_inscricao_por_setor.pkl
    features_producao.json
    fill_medians_producao.json
    modelo_lightgbm_apartamentos.txt
    teste_final_previsoes_promovido.parquet

Se os arquivos vierem nas pastas originais do projeto
(entrega_equipe_20260615, Modelo_Apartamentos_Aprovado, projeto_itiv), rode:

  python -m scripts.organizar_importacao

Isso copia os artefatos para pronto/ (nomes canônicos), coloca o modelo em
dados_modelo/ e move as árvores originais para dados_importacao/_origem/.

Depois:

  docker compose run --rm web python -m scripts.popular_base --recriar
  docker compose up -d web

Sem esses arquivos, use o recorte sintético:

  docker compose run --rm web python -m scripts.popular_base --demo --recriar
