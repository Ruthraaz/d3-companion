@echo off
rem Abre o D3 Companion (janela + overlay). Dois cliques neste arquivo.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Falta a .venv. Veja "Como rodar" no README.md.
  pause
  exit /b 1
)
.venv\Scripts\python.exe src\janela.py
if errorlevel 1 pause
