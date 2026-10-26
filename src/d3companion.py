"""
Ponto de entrada do .exe (PyInstaller). O mesmo programa faz os dois papéis:

    D3 Companion.exe              abre a janela (e ela liga o overlay)
    D3 Companion.exe --overlay    o overlay do jogo (a janela é quem abre este)

Do código continua igual: python src/janela.py.
"""

import os
import sys


def main():
    # Programa sem console: o Windows não dá saída padrão. A janela lê o que o
    # overlay imprime por um "cano"; sem cano, o texto vai pro lixo.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = sys.stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # o log chega na hora na janela

    import pastas
    pastas.preparar()
    if "--overlay" in sys.argv[1:]:
        import app
        app.main()
    else:
        import janela
        janela.main()


if __name__ == "__main__":
    main()
