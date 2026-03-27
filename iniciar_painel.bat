@echo off
title Painel Multi-Agente Analytics
cd /d "%~dp0"

echo Iniciando o Painel do LLM E-commerce...

streamlit run app.py

pause
