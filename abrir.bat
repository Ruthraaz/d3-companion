@echo off
rem Abre o D3 Companion pelo código (janela + overlay). Dois cliques neste arquivo.
rem Usa o pythonw (Python sem console): o cmd fecha sozinho e fica só a janela.
rem Pra ver erros no console: .venv\Scripts\python.exe src\janela.py
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Falta a .venv. Veja "Como rodar" no README.md.
  pause
  exit /b 1
)
start "" .venv\Scripts\pythonw.exe src\janela.py
