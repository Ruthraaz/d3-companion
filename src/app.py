"""
O app: passe o mouse num item no jogo (ou aperte o F8 em cima dele).

    print perto do mouse -> recorta a dica -> OCR -> parser -> avaliador
       -> selo no overlay, ao lado da dica (e o resumo no terminal)

Dois jeitos de disparar (dá pra usar os dois juntos):
  - automático (AUTOMATICO=sim no .env): o app olha a tela sozinho e avalia
    cada dica nova que aparece; o selo fica enquanto a dica estiver na tela;
  - atalho (ATALHO, padrão F8): avalia na hora, e o selo some em SELO_SEGUNDOS.

Uso:
    python src/app.py                    (fica esperando o F8; Ctrl+C pra sair)
    python src/app.py --testar <print>   (mostra o selo de um print salvo no meio da tela)

O jogo precisa estar em "Tela cheia em janela" (Windowed Fullscreen).
O atalho usa o RegisterHotKey do próprio Windows: o app não lê a memória do
jogo nem se injeta nele, só olha a tela.

Como as partes conversam:
  - a janela do selo (Qt) roda na thread principal;
  - o F8 e o vigia (modo automático) rodam cada um numa thread, fazem o
    trabalho pesado (print + OCR levam ~1 s) sem travar a interface e avisam
    o selo por um SINAL do Qt. Uma trava impede dois OCR ao mesmo tempo.
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

import historico  # noqa: E402
from avaliador import builds_escolhidas, ler_builds, resumo, texto_dos_problemas  # noqa: E402
from config import ler_config  # noqa: E402
from atalho import ler_atalho, registrar, sugestoes_livres  # noqa: E402
from captura import capturar_perto_do_cursor, jogo_em_foco, olhada_rapida  # noqa: E402
from nucleo import avaliar_print, caixa_na_tela, montar_selo, processo_vivo  # noqa: E402
from overlay import JanelaSelo  # noqa: E402
from vigia import AVALIAR, ESCONDER, GUARDADO, Vigia  # noqa: E402

WM_HOTKEY = 0x0312
ATALHO = os.getenv("ATALHO", "F8")                         # .env pode mudar
SEGUNDOS_DO_SELO = float(os.getenv("SELO_SEGUNDOS", "6"))  # .env pode mudar
INTERVALO_DO_VIGIA = 0.25  # segundos entre olhadas (cada uma custa ~40 ms)
FIXO = 0                   # selo sem tempo pra sumir: some quando a dica sumir

_avaliando = threading.Lock()  # F8 e vigia nunca fazem OCR ao mesmo tempo


class Ponte(QObject):
    """Leva os pedidos da thread do F8 até a janela do selo."""
    mostrar = Signal(object, object, float)  # (Selo, caixa da dica na tela, segundos; 0 = fixo)
    esconder = Signal()


def _terminal(av) -> str:
    if av.erro:
        texto = av.erro
    else:
        texto = resumo(av.item, av.resultados)
    nome = av.arquivo.name if av.arquivo else "-"
    return f"{texto}\n({av.segundos:.1f}s · capturas/{nome})"


_trava = None  # o Windows apaga a trava sozinho quando o processo termina


def _unico_overlay() -> bool:
    """Só um overlay por vez. Com dois abertos (ex.: um esquecido no terminal),
    cada um responde a uma tecla e o selo parece "ignorar" a build escolhida
    (aconteceu em 24/10/2026). Usa um mutex com nome do Windows como trava."""
    global _trava
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    _trava = kernel32.CreateMutexW(None, False, "Local\\D3Companion.Overlay")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def ouvir_atalho(ponte: Ponte, builds: list[dict], pronto: threading.Event, falhou: list):
    """Roda na thread do atalho. O atalho fica preso a esta thread."""
    user32 = ctypes.windll.user32
    if not registrar(ATALHO):
        falhou.append(True)
        pronto.set()
        return
    pronto.set()

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message != WM_HOTKEY:
            continue
        # O selo não aparece no print (overlay._fora_dos_prints), então nem
        # precisa esconder antes.
        imagem, cursor, origem = capturar_perto_do_cursor()
        av, selo, caixa = avaliar(imagem, cursor, origem, builds)
        ponte.mostrar.emit(selo, caixa, SEGUNDOS_DO_SELO)


def avaliar(imagem, cursor, origem, builds, automatico=False):
    """O caminho comum do F8 e do vigia: avalia, registra no histórico e
    devolve (avaliação, selo, caixa da dica na tela)."""
    with _avaliando:
        # A build escolhida na janela vale na hora: o .env é relido a cada vez.
        usadas = builds_escolhidas(builds, ler_config()["BUILD_ATIVA"])
        av = avaliar_print(imagem, cursor, usadas, salvar_sem_dica=not automatico)
        selo = montar_selo(av)
        if not (automatico and av.erro):  # alarme falso do vigia não vai pro histórico
            print("\n" + _terminal(av), flush=True)
            com = usadas[0].get("apelido", usadas[0]["nome"]) if len(usadas) == 1 else "Todas"
            historico.registrar(av, selo, com=com)  # a janela principal lê daqui
        return av, selo, caixa_na_tela(av, origem, cursor)


def vigiar(ponte: Ponte, builds: list[dict]):
    """Modo automático: olha a tela a cada INTERVALO_DO_VIGIA e avalia cada
    dica nova sozinho. Só olha com o Diablo III em primeiro plano."""
    vigia = Vigia()
    config, proxima_leitura = ler_config(), 0.0
    while True:
        time.sleep(INTERVALO_DO_VIGIA)
        if time.monotonic() >= proxima_leitura:  # a janela pode ligar/desligar a qualquer hora
            config, proxima_leitura = ler_config(), time.monotonic() + 1
        if config["AUTOMATICO"] != "sim" or not jogo_em_foco():
            if vigia.esquecer_tela():
                ponte.esconder.emit()
            continue

        imagem, cursor, origem = capturar_perto_do_cursor()
        assinatura = olhada_rapida(imagem, cursor)
        if assinatura is not None:
            # Trocar a build na janela tem que reavaliar a mesma dica.
            assinatura = (config["BUILD_ATIVA"],) + assinatura
        acao, guardado = vigia.olhar(assinatura)
        if acao == ESCONDER:
            ponte.esconder.emit()
        elif acao == GUARDADO:
            ponte.mostrar.emit(*guardado, FIXO)
        elif acao == AVALIAR:
            # A tela está parada há uma olhada: avalia o print que já temos.
            av, selo, caixa = avaliar(imagem, cursor, origem, builds, automatico=True)
            if av.erro:  # dica de habilidade, menu etc.: fica quieto e não tenta de novo
                vigia.guardar(assinatura, None)
            else:
                vigia.guardar(assinatura, (selo, caixa))
                ponte.mostrar.emit(selo, caixa, FIXO)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    builds, problemas = ler_builds()
    if problemas:  # build com erro fica de fora; as outras funcionam
        print(texto_dos_problemas(problemas), flush=True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    selo = JanelaSelo(SEGUNDOS_DO_SELO)

    # Ctrl+C no terminal fecha o app (o Qt precisa "acordar" de vez em quando pra notar).
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    acordar = QTimer()
    acordar.timeout.connect(lambda: None)
    acordar.start(200)

    # Aberto pela janela: fecha junto com ela. Sem isso, se a janela morre sem
    # avisar (ex.: fechar o terminal do abrir.bat), o overlay fica órfão,
    # segura a trava e o da próxima janela aparece "parado" (24/10/2026).
    pid_da_janela = os.environ.get("D3_JANELA_PID")
    if pid_da_janela:
        def conferir_janela():
            if not processo_vivo(int(pid_da_janela)):
                print("A janela fechou: fechando o overlay junto.", flush=True)
                app.quit()
        vigia_da_janela = QTimer()
        vigia_da_janela.timeout.connect(conferir_janela)
        vigia_da_janela.start(2000)

    if len(sys.argv) >= 3 and sys.argv[1] == "--testar":
        # Mesmo caminho do F8, mas com um print salvo; o selo aparece no meio da tela.
        av = avaliar_print(Image.open(sys.argv[2]), None, builds, salvar=False)
        print(_terminal(av))
        g = app.primaryScreen().geometry()
        largura = av.caixa[2] - av.caixa[0] if av.caixa else 400
        x0 = g.center().x() - largura // 2
        selo.mostrar(montar_selo(av), (x0, g.top() + 150, x0 + largura, g.top() + 700), SEGUNDOS_DO_SELO)
        QTimer.singleShot(int(SEGUNDOS_DO_SELO * 1000) + 300, app.quit)
        app.exec()
        return

    if not _unico_overlay():
        print("Já tem um D3 Companion (overlay) aberto — talvez num terminal ou noutra janela.\n"
              "Feche aquele primeiro (Ctrl+C no terminal dele) e tente de novo.")
        sys.exit(1)

    try:
        ler_atalho(ATALHO)
    except ValueError as erro:
        print(f"ATALHO={ATALHO} no .env não é válido ({erro}). Exemplos: F8, Ctrl+F8, Alt+Q.")
        sys.exit(1)

    ponte = Ponte()
    ponte.mostrar.connect(selo.mostrar)
    ponte.esconder.connect(selo.hide)
    pronto, falhou = threading.Event(), []
    threading.Thread(target=ouvir_atalho, args=(ponte, builds, pronto, falhou), daemon=True).start()
    threading.Thread(target=vigiar, args=(ponte, builds), daemon=True).start()
    pronto.wait()
    if falhou:
        livres = ", ".join(sugestoes_livres(evitar=ATALHO)) or "nenhuma das sugestões"
        print(f"Não consegui registrar o {ATALHO}: outro programa já está usando essa tecla.\n"
              f"Teclas livres agora: {livres}.\n"
              "Escolha uma e coloque no .env, ex.: ATALHO=Ctrl+F8 (veja .env.example).")
        sys.exit(1)

    modo = ("passe o mouse num item (avaliação automática) ou aperte "
            if ler_config()["AUTOMATICO"] == "sim" else "passe o mouse num item e aperte ")
    print(f"D3 Companion rodando com {len(builds)} builds: {modo}{ATALHO}. (Ctrl+C pra sair)", flush=True)
    app.exec()
    print("Até mais!")


if __name__ == "__main__":
    main()
