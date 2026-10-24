"""
Etapa 4 — O app: aperte F8 com o mouse em cima de um item no jogo.

    F8 -> print perto do mouse -> recorta a dica -> OCR -> parser -> avaliador

Por enquanto o resultado sai no terminal; o overlay em cima do jogo é a Etapa 5.
Cada dica recortada é salva em capturas/ (fora do Git): serve pra investigar
erro de leitura e pra virar exemplo novo nos testes.

Uso:
    python src/app.py                    (fica esperando o F8; Ctrl+C pra sair)
    python src/app.py --testar <print>   (roda o mesmo caminho com um print salvo)

O jogo precisa estar em "Tela cheia em janela" (Windowed Fullscreen).
O atalho usa o RegisterHotKey do próprio Windows: o app não lê a memória do
jogo nem se injeta nele, só olha a tela.
"""

import ctypes
import ctypes.wintypes
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from avaliador import avaliar_todas, carregar_builds, resumo
from captura import AMPLIAR, capturar_perto_do_cursor, recortar_dica
from ocr import ler_texto
from parser import interpretar

TECLA = 0x77            # F8 (códigos "VK_" do Windows)
MOD_NOREPEAT = 0x4000   # segurar a tecla não dispara várias vezes
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
PASTA_CAPTURAS = Path(__file__).resolve().parent.parent / "capturas"


def processar(imagem: Image.Image, cursor: tuple[int, int] | None, builds: list[dict]) -> str:
    """Do print ao veredito. Devolve o texto pra mostrar."""
    inicio = time.perf_counter()
    PASTA_CAPTURAS.mkdir(exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")

    recorte = recortar_dica(imagem, cursor)
    if recorte is None:
        imagem.save(PASTA_CAPTURAS / f"{carimbo}_sem_dica.png")
        return ("Não achei a dica perto do mouse. O mouse estava em cima do item?\n"
                f"(o print foi salvo em capturas/{carimbo}_sem_dica.png pra investigar)")
    recorte.save(PASTA_CAPTURAS / f"{carimbo}.png")

    try:
        item = interpretar(ler_texto(recorte, ampliar=AMPLIAR))
    except ValueError as erro:
        return f"Li a dica, mas não entendi o item: {erro} (recorte em capturas/{carimbo}.png)"

    texto = resumo(item, avaliar_todas(item, builds))
    return texto + f"\n({time.perf_counter() - inicio:.1f}s · recorte em capturas/{carimbo}.png)"


def esperar_atalho(builds: list[dict]):
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, MOD_NOREPEAT, TECLA):
        print("Não consegui registrar o F8. Outro programa já está usando essa tecla?")
        sys.exit(1)
    print("D3 Companion rodando. Passe o mouse num item e aperte F8. (Ctrl+C pra sair)")

    msg = ctypes.wintypes.MSG()
    try:
        while True:
            # PeekMessage não trava esperando, então o Ctrl+C continua funcionando.
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    imagem, cursor = capturar_perto_do_cursor()
                    print("\n" + processar(imagem, cursor, builds))
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nAté mais!")
    finally:
        user32.UnregisterHotKey(None, 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    builds = carregar_builds()
    if len(sys.argv) >= 3 and sys.argv[1] == "--testar":
        print(processar(Image.open(sys.argv[2]), None, builds))
    else:
        esperar_atalho(builds)
