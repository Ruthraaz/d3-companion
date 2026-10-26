"""
Onde ficam as coisas do app.

Rodando do código (python src/janela.py): tudo na pasta do projeto, como sempre.

No .exe (PyInstaller): os arquivos do programa ficam junto do executável e só
são lidos; o que é seu (.env, builds, prints, cache) fica em
%APPDATA%\\D3 Companion — assim, trocar o .exe por uma versão nova não apaga nada.
"""

import os
import shutil
import sys
from pathlib import Path

NO_EXE = bool(getattr(sys, "frozen", False))

if NO_EXE:
    PROGRAMA = Path(sys._MEIPASS)  # o que o PyInstaller empacotou (web/, builds/ de exemplo, tesseract/)
    SEUS = Path(os.environ.get("APPDATA") or Path.home()) / "D3 Companion"
    WEB = PROGRAMA / "web"
else:
    PROGRAMA = SEUS = Path(__file__).resolve().parent.parent
    WEB = PROGRAMA / "src" / "web"

ARQUIVO_ENV = SEUS / ".env"
PASTA_BUILDS = SEUS / "builds"
PASTA_CAPTURAS = SEUS / "capturas"
PASTA_DADOS = SEUS / "dados"
TESSERACT_JUNTO = PROGRAMA / "tesseract" / "tesseract.exe"  # só existe no .exe


def preparar() -> None:
    """No .exe, na primeira vez: cria a pasta do usuário e copia as builds de
    exemplo. Nunca sobrescreve uma build que já está lá."""
    if not NO_EXE:
        return
    PASTA_BUILDS.mkdir(parents=True, exist_ok=True)
    for exemplo in (PROGRAMA / "builds").glob("*.json"):
        destino = PASTA_BUILDS / exemplo.name
        if not destino.exists():
            shutil.copyfile(exemplo, destino)
