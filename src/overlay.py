"""
Etapa 5 — Overlay: o selo que aparece em cima do jogo, ao lado da dica.

Visual (decidido em 24/10/2026): selo pequeno, fundo escuro semitransparente,
borda verde (serve) ou vermelha (não serve), nome da build em destaque,
afixos com ✓/✗. Some sozinho depois de alguns segundos.

O selo é uma janela SEPARADA do jogo:
  - sempre por cima, sem moldura;
  - deixa o clique passar (o mouse "atravessa" o selo);
  - nunca pega o foco (senão o jogo em tela cheia poderia minimizar).
Por isso o jogo precisa estar em "Tela cheia em janela".

Este arquivo só DESENHA. O que mostrar vem pronto do núcleo (nucleo.Selo).
"""

import ctypes
import html

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from nucleo import Caixa, Selo, posicao_do_selo

# Estilo que lembra o Diablo (escuro, dourado), sem copiar arte da Blizzard.
CORES = {
    "borda_serve": "#3fb950",
    "borda_nao_serve": "#e5534b",
    "borda_parcial": "#d29922",
    "fundo": "rgba(14, 11, 8, 225)",
    "titulo": "#d8b26a",
    "build": "#f0c86e",
    "normal": "#e6e1d6",
    "ok": "#7ee787",
    "falta": "#ff7b72",
    "motivo": "#c9c1b0",
}

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def _html_da_linha(linha: list[tuple[str, str]]) -> str:
    partes = []
    for texto, estilo in linha:
        peso = "bold" if estilo == "build" else "normal"
        partes.append(f'<span style="color:{CORES[estilo]}; font-weight:{peso}">'
                      f"{html.escape(texto).replace('  ', '&nbsp;&nbsp;')}</span>")
    return "".join(partes)


class JanelaSelo(QWidget):
    def __init__(self, segundos: float = 6.0, gravacao: bool = False):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.moldura = QFrame(self)
        self.titulo = QLabel(self.moldura)
        self.corpo = QLabel(self.moldura)
        self.corpo.setTextFormat(Qt.TextFormat.RichText)
        dentro = QVBoxLayout(self.moldura)
        dentro.setContentsMargins(12, 8, 12, 9)
        dentro.setSpacing(3)
        dentro.addWidget(self.titulo)
        dentro.addWidget(self.corpo)
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.addWidget(self.moldura)

        self.gravacao = gravacao  # modo gravação: o selo aparece nas gravações de tela
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.segundos = segundos

    def preencher(self, selo: Selo):
        borda = (CORES["borda_serve"] if selo.serve
                 else CORES["borda_parcial"] if selo.parcial else CORES["borda_nao_serve"])
        self.moldura.setStyleSheet(
            f"QFrame {{ background: {CORES['fundo']}; border: 2px solid {borda}; border-radius: 7px; }}"
            "QLabel { border: none; background: transparent;"
            " font-family: 'Segoe UI', sans-serif; font-size: 10.5pt; }")
        self.titulo.setStyleSheet(f"color: {CORES['titulo']}; font-weight: bold; font-size: 9.5pt;")
        self.titulo.setText(selo.titulo)
        self.corpo.setText("<br>".join(_html_da_linha(l) for l in selo.linhas))
        self.adjustSize()

    def mostrar(self, selo: Selo, caixa_na_tela: Caixa, segundos: float | None = None):
        """Mostra o selo ao lado da dica (coordenadas de tela) e agenda o sumiço.
        `segundos=0`: fica até alguém mandar esconder (modo automático, que
        esconde quando a dica some)."""
        self.preencher(selo)
        tela = QGuiApplication.screenAt(self._centro(caixa_na_tela)) or QGuiApplication.primaryScreen()
        g = tela.geometry()
        x, y = posicao_do_selo(caixa_na_tela, (self.width(), self.height()),
                               (g.left(), g.top(), g.right() + 1, g.bottom() + 1))
        self.move(x, y)
        self.show()
        self._nunca_pegar_foco()
        self.raise_()
        segundos = self.segundos if segundos is None else segundos
        if segundos > 0:
            self.timer.start(int(segundos * 1000))
        else:
            self.timer.stop()

    @staticmethod
    def _centro(caixa: Caixa) -> QPoint:
        return QPoint((caixa[0] + caixa[2]) // 2, (caixa[1] + caixa[3]) // 2)

    def _nunca_pegar_foco(self):
        """Reforço pelo próprio Windows: não ativar, deixar o clique passar."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            estilo = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
                                  | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
            # Fora dos prints: o selo some da captura de tela (o jogador continua
            # vendo). Sem isso o modo automático veria o próprio selo, acharia que
            # a tela mudou e reavaliaria sem parar. Windows 10 2004 ou mais novo.
            # No modo gravação fica visível (pro OBS pegar); aí o automático
            # fica desligado e o atalho esconde o selo antes do print (app.py).
            if not self.gravacao:
                user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except (AttributeError, OSError):
            pass
