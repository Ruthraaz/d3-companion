"""
Janela principal (depois da versão 1): builds no boneco, histórico e configurações.

Uso:
    python src/janela.py

A janela é HTML/CSS/JS (pasta src/web/) aberta pelo pywebview, que usa o
WebView2 do próprio Windows (o mesmo motor do Edge), sem Chromium embutido.

Como as partes conversam:
  - a janela LIGA o overlay (src/app.py) como outro processo. Os dois usam a
    thread principal (Qt e pywebview), por isso não cabem no mesmo processo;
  - o overlay grava cada avaliação em capturas/historico.jsonl, a janela lê;
  - o JavaScript chama os métodos da classe Api (pywebview faz a ponte).
Fechar a janela desliga o overlay junto.
"""

import base64
import io
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

import webview
from PIL import Image

import historico
from avaliador import carregar_builds, ficha_da_build
from config import ler_config, salvar_config
from nucleo import PASTA_CAPTURAS

PASTA_SRC = Path(__file__).resolve().parent
PAGINA = PASTA_SRC / "web" / "index.html"
LARGURA_MINIATURA = 220


class Overlay:
    """O processo do overlay (src/app.py): liga, desliga e guarda o que ele imprime."""

    def __init__(self):
        self._processo: subprocess.Popen | None = None
        self.log: deque[str] = deque(maxlen=200)

    def ligar(self):
        self.desligar()
        self.log.clear()
        self._processo = subprocess.Popen(
            [sys.executable, "-u", str(PASTA_SRC / "app.py")],  # -u: log na hora, sem buffer
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._ler_saida, args=(self._processo,), daemon=True).start()

    def _ler_saida(self, processo: subprocess.Popen):
        for linha in processo.stdout:
            self.log.append(linha.rstrip())

    def desligar(self):
        if self._processo and self._processo.poll() is None:
            # /T derruba a "árvore": o python.exe da .venv é só um lançador que abre
            # outro python.exe, e é esse filho que segura o atalho. Só o terminate()
            # deixaria o filho vivo e o F8 ocupado.
            subprocess.run(["taskkill", "/PID", str(self._processo.pid), "/T", "/F"],
                           capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self._processo.wait(timeout=5)

    def estado(self) -> dict:
        rodando = bool(self._processo) and self._processo.poll() is None
        return {"rodando": rodando, "log": list(self.log)[-40:]}


class Api:
    """O que o JavaScript pode chamar: window.pywebview.api.<método>()."""

    def __init__(self, overlay: Overlay):
        self._overlay = overlay  # com "_" o pywebview não expõe pro JavaScript

    def builds(self) -> list[dict]:
        return [ficha_da_build(b) for b in carregar_builds()]

    def historico(self, limite: int = 50) -> list[dict]:
        return historico.ler(limite)

    def miniatura(self, nome: str) -> str | None:
        """Recorte salvo em capturas/ como imagem pequena (data URI) pra lista."""
        arquivo = PASTA_CAPTURAS / Path(nome).name  # só arquivos de capturas/
        if not arquivo.is_file():
            return None
        img = Image.open(arquivo).convert("RGB")
        img.thumbnail((LARGURA_MINIATURA, LARGURA_MINIATURA * 3))
        buffer = io.BytesIO()
        img.save(buffer, "JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()

    def config(self) -> dict:
        return ler_config()

    def salvar_config(self, mudancas: dict) -> dict:
        erros = salvar_config(mudancas)
        if not erros:
            self._overlay.ligar()  # o overlay lê o .env só ao abrir
        return {"erros": erros}

    def estado(self) -> dict:
        return self._overlay.estado() | {"config": ler_config()}

    def reiniciar_overlay(self) -> dict:
        self._overlay.ligar()
        return self._overlay.estado()


def main():
    overlay = Overlay()
    overlay.ligar()
    janela = webview.create_window(
        "D3 Companion", str(PAGINA), js_api=Api(overlay),
        width=1180, height=780, min_size=(900, 600), background_color="#0e0c0a",
    )
    janela.events.closed += overlay.desligar
    webview.start()
    overlay.desligar()


if __name__ == "__main__":
    main()
