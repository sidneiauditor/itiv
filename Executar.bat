@echo off
chcp 65001 >nul
title TranscritorAI
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo Ambiente virtual não encontrado.
    echo Execute primeiro "Instalar dependências.bat"
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python transcritor\main.py

if errorlevel 1 (
    echo.
    echo [ERRO] O aplicativo encerrou com erro.
    pause
)
