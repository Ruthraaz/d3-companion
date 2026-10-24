"""
O app: aperte F8 com o mouse em cima de um item no jogo.

    F8 -> print perto do mouse -> recorta a dica -> OCR -> parser -> avaliador
       -> selo no overlay, ao lado da dica (e o resumo no terminal)

Uso:
    python src/app.py                    (fica esperando o F8; Ctrl+C pra sair)
    python src/app.py --testar <print>   (mostra o selo de um print salvo no meio da tela)

O jogo precisa estar em "Tela cheia em janela" (Windowed Fullscreen).
O atalho usa o RegisterHotKey do próprio Windows: o app não lê a memória do
jogo nem se injeta nele, só olha a tela.

Como as partes conversam:
  - a janela do selo (Qt) roda na thread principal;
  - o F8 é ouvido numa thread separada, que faz o trabalho pesado (print + OCR
    levam ~1 s) sem travar a interface, e avisa o selo por um SINAL do Qt.
"""

import ctypes
import ctypes.wintypes
import os
import signal
import sys
import threading
import time

# O print e a posição do mouse usam pixels reais da tela; o selo também precisa
# usar, senão com zoom de tela (ex.: 125%) ele apareceria no lugar errado.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PIL import Image  # noqa: E402
from PySide6.QtCore import QObject, QTimer, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from avaliador import carregar_builds, resumo  # noqa: E402
from captura import capturar_perto_do_cursor  # noqa: E402
from nucleo import avaliar_print, caixa_na_tela, montar_selo  # noqa: E402
from overlay import JanelaSelo  # noqa: E402

TECLA = 0x77            # F8 (códigos "VK_" do Windows)
MOD_NOREPEAT = 0x4000   # segurar a tecla não dispara várias vezes
WM_HOTKEY = 0x0312
SEGUNDOS_DO_SELO = float(os.getenv("SELO_SEGUNDOS", "6"))  # .env pode mudar


class Ponte(QObject):
    """Leva os pedidos da thread do F8 até a janela do selo."""
    mostrar = Signal(object, object)  # (Selo, caixa da dica na tela)
    esconder = Signal()


def _terminal(av) -> str:
    if av.erro:
        texto = av.erro
    else:
        texto = resumo(av.item, av.resultados)
    nome = av.arquivo.name if av.arquivo else "-"
    return f"{texto}\n({av.segundos:.1f}s · capturas/{nome})"


def ouvir_atalho(ponte: Ponte, builds: list[dict], pronto: threading.Event, falhou: list):
    """Roda na thread do F8. O atalho fica preso a esta thread."""
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, MOD_NOREPEAT, TECLA):
        falhou.append(True)
        pronto.set()
        return
    pronto.set()

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message != WM_HOTKEY:
            continue
        # Esconde o selo anterior pra ele não aparecer no print.
        ponte.esconder.emit()
        time.sleep(0.12)
        imagem, cursor, origem = capturar_perto_do_cursor()
        av = avaliar_print(imagem, cursor, builds)
        print("\n" + _terminal(av), flush=True)
        ponte.mostrar.emit(montar_selo(av), caixa_na_tela(av, origem, cursor))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    builds = carregar_builds()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    selo = JanelaSelo(SEGUNDOS_DO_SELO)

    # Ctrl+C no terminal fecha o app (o Qt precisa "acordar" de vez em quando pra notar).
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    acordar = QTimer()
    acordar.timeout.connect(lambda: None)
    acordar.start(200)

    if len(sys.argv) >= 3 and sys.argv[1] == "--testar":
        # Mesmo caminho do F8, mas com um print salvo; o selo aparece no meio da tela.
        av = avaliar_print(Image.open(sys.argv[2]), None, builds, salvar=False)
        print(_terminal(av))
        g = app.primaryScreen().geometry()
        largura = av.caixa[2] - av.caixa[0] if av.caixa else 400
        x0 = g.center().x() - largura // 2
        selo.mostrar(montar_selo(av), (x0, g.top() + 150, x0 + largura, g.top() + 700))
        QTimer.singleShot(int(SEGUNDOS_DO_SELO * 1000) + 300, app.quit)
        app.exec()
        return

    ponte = Ponte()
    ponte.mostrar.connect(selo.mostrar)
    ponte.esconder.connect(selo.hide)
    pronto, falhou = threading.Event(), []
    threading.Thread(target=ouvir_atalho, args=(ponte, builds, pronto, falhou), daemon=True).start()
    pronto.wait()
    if falhou:
        print("Não consegui registrar o F8. Outro programa já está usando essa tecla?")
        sys.exit(1)

    print(f"D3 Companion rodando com {len(builds)} builds. "
          "Passe o mouse num item e aperte F8. (Ctrl+C pra sair)", flush=True)
    app.exec()
    print("Até mais!")


if __name__ == "__main__":
    main()
