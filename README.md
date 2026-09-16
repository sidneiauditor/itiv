# Avaliador ITIV

Aplicação web (FastAPI + PostgreSQL + Docker) para avaliação de **apartamentos** com compra e venda registrada — Coordenadoria de Inteligência Fiscal / SEFAZ Salvador.

O valor estimado é **subsídio técnico**; a decisão fiscal permanece do auditor.

Detalhamento técnico: [`arquitetura.md`](arquitetura.md).

**Fluxo de implantação:** o código sobe no servidor; a **carga do Postgres sai da sua máquina**; o **modelo LightGBM** vai por `scp`.

---

## Portas

| Serviço | Porta no host | Porta no container |
|---------|---------------|--------------------|
| Avaliador web | **8084** | 8766 |
| PostgreSQL | **8085** | 5432 |

Acesso: `http://<servidor>:8084`

Caminho no servidor: `/opt/itiv`

---

## 1. No servidor — código, banco e web

```bash
cd /opt/itiv
cp .env.example .env
```

Edite o `.env`: senha do Postgres e, se usar mapa/Street View, `GOOGLE_SV_KEY`.

```bash
docker compose up -d db
docker compose build web
docker compose up -d web
```

Neste momento o `/health` pode mostrar `"modelo": false` até o passo 3. A carga das tabelas é o passo 2.

---

## 2. Na sua máquina — carga do Postgres

Os Parquet/CSV **não** vão para o servidor. O script lê `dados_importacao/pronto/` localmente e grava no banco remoto (porta **8085**).

Arquivos esperados em `D:\Projetos\Apps\itiv\dados_importacao\pronto\`:

```
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
```

Se os dados ainda estiverem nas pastas originais do projeto, organize uma vez:

```powershell
.\.venv\Scripts\python -m scripts.organizar_importacao
```

**Não use o Python do Anaconda.** Ambiente do projeto (só na primeira vez):

```powershell
cd D:\Projetos\Apps\itiv
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

Carga (ajuste usuário, host e senha). `--recriar` **apaga** as tabelas no servidor e importa de novo:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://itiv:SENHA@valedosrios.sefaz.net:8085/itiv"
$env:ITIV_DADOS_DIR = "D:\Projetos\Apps\itiv\dados_importacao"
$env:MODELO_DIR = "D:\Projetos\Apps\itiv\dados_modelo"
.\.venv\Scripts\python -m scripts.popular_base --recriar
```

Espere `Carga concluída.` A primeira carga demora (centenas de milhares de linhas pela rede).

---

## 3. Na sua máquina — `scp` do modelo

O avaliador **não** lê o LightGBM do banco. O arquivo precisa existir em `/opt/itiv/dados_modelo/` no servidor.

O usuário de SSH em geral **não grava** direto em `/opt/itiv`. Envie para a home e mova com `sudo`.

Na sua máquina:

```powershell
scp D:\Projetos\Apps\itiv\dados_modelo\modelo_lightgbm_apartamentos.txt guaquim@valedosrios.sefaz.net:~/
```

No servidor:

```bash
sudo mkdir -p /opt/itiv/dados_modelo
sudo mv ~/modelo_lightgbm_apartamentos.txt /opt/itiv/dados_modelo/
cd /opt/itiv
docker compose restart web
curl http://localhost:8084/health
```

Esperado: `"db": true`, `"modelo": true` e `pool` na casa das dezenas de milhares.

Abra `http://<servidor>:8084`.

Se o `scp` direto para `/opt/itiv/dados_modelo/` der `Permission denied`, use exatamente essa sequência (home + `sudo mv`).

---

## Recarga (nova extração ou novo modelo)

- **Só dados:** na sua máquina, rode de novo o passo 2 e no servidor `docker compose restart web`.
- **Só modelo:** passo 3 de novo.

---

## O que o Git não traz

`dados_importacao/`, `dados_modelo/` (artefatos), `*.xlsx`, `*.parquet`, `*.pkl` e `.env` não entram no clone. Permanecem na sua máquina; no servidor ficam o Postgres (volume Docker `itiv_pg`) e o `.txt` do modelo.
