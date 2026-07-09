@echo off
chcp 65001 >nul
title TranscritorAI - Instalar dependências
cd /d "%~dp0"

echo ============================================
echo   TranscritorAI - Instalação de dependências
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python não encontrado no PATH.
    echo Instale Python 3.13 em https://www.python.org/downloads/
    echo Marque a opção "Add Python to PATH" durante a instalação.
    pause
    exit /b 1
)

python --version
echo.

if not exist "venv" (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
)

echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo.
echo Instalando dependências (pode demorar alguns minutos)...
pip install --upgrade pip
pip install -r transcritor\requirements.txt
pip install windnd

if errorlevel 1 (
    echo.
    echo [ERRO] Falha na instalação das dependências.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Instalação concluída com sucesso!
echo   Execute "Executar.bat" para iniciar o app.
echo ============================================
echo.
pause
