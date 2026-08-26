@echo off
chcp 65001 > nul
cd /d "%~dp0app"
echo Iniciando o Avaliador ITIV - Apartamentos com idade (carrega o modelo, ~1 minuto)...
echo Quando aparecer "Pronto", abra no navegador: http://localhost:8766
python avaliador_web_apartamentos.py
pause
