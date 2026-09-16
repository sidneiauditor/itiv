@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Subindo PostgreSQL e o avaliador web (Docker)...
docker compose up -d db
docker compose run --rm web python -m scripts.popular_base --demo --recriar
docker compose up -d web
echo.
echo Abra http://localhost:8766
echo SQ de teste (demo): 900001
pause
