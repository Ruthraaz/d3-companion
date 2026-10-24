"""
Janela principal (depois da versão 1): builds no boneco, histórico e configurações.

Uso:
    python src/janela.py      (ou dois cliques em abrir.bat, na raiz do projeto)

Funciona até sem ativar a .venv: se faltar o pywebview, o arquivo se abre de
novo com o Python da .venv.

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
import webbrowser
from collections import deque
from pathlib import Path

PYTHON_DA_VENV = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"

try:
    import webview
except ImportError:
    # Rodou com o Python do Windows (sem a .venv ativada): ele não tem o
    # pywebview. Em vez de só dar erro, abre de novo com o Python da .venv.
    if PYTHON_DA_VENV.exists() and Path(sys.executable).resolve() != PYTHON_DA_VENV.resolve():
        sys.exit(subprocess.call([str(PYTHON_DA_VENV), __file__, *sys.argv[1:]]))
    sys.exit("Falta o pywebview. Na pasta do projeto, rode:\n"
             "    .venv\\Scripts\\activate\n"
             "    pip install -r requirements.txt")
from PIL import Image

import historico
from avaliador import ficha_da_build, ler_builds, problemas_da_build
from blizzard import Blizzard, ErroBlizzard, visual_da_build
from config import ler_config, salvar_config
from maxroll import (ErroMaxroll, baixar_planner, classe_do_planner, e_de_seguidor, montar,
                     nomes_dos_perfis, planners_do_link, salvar_build)
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
        self._blizzard = Blizzard()  # um só: o token vale 24 h
        self._planners = {}  # número -> planner do Maxroll já baixado (entre buscar e importar)

    def builds(self) -> list[dict]:
        return [ficha_da_build(b) for b in ler_builds()[0]]

    def visual(self, id_build: str) -> dict:
        """Ícones e textos em português da build (API da Blizzard, com cache).
        {"erro": mensagem} se faltar chave ou internet: a tela mostra sem ícones."""
        build = next((b for b in ler_builds()[0] if b["id"] == id_build), None)
        if build is None:
            return {"erro": f"Build {id_build!r} não encontrada."}
        try:
            return visual_da_build(build, self._blizzard)
        except ErroBlizzard as e:
            return {"erro": str(e)}

    def buscar_maxroll(self, texto: str) -> dict:
        """Link de guia ou de planner do Maxroll -> builds que ele traz, com os
        perfis de cada uma. As do seguidor ficam de fora."""
        try:
            planners = [baixar_planner(n) for n in planners_do_link(texto)]
        except ErroMaxroll as e:
            return {"erro": str(e)}
        herois = [p for p in planners if not e_de_seguidor(p) and classe_do_planner(p)]
        if not herois:
            return {"erro": "Esse link não tem build de herói que o app conheça."}
        self._planners.update({p["_numero"]: p for p in herois})
        return {"builds": [{
            "numero": p["_numero"],
            "nome": p["_nome"],
            "classe": classe_do_planner(p),
            "perfis": nomes_dos_perfis(p),
            "perfil": p.get("activeProfile") or 0,
        } for p in herois]}

    def importar_maxroll(self, numero: int, perfil: int, apelido: str = "") -> dict:
        """Grava a build escolhida em builds/ (nunca sobrescreve). {"id"} ou {"erro"}."""
        planner = self._planners.get(int(numero))
        if planner is None:
            return {"erro": "Busque o link de novo antes de importar."}
        try:
            build = montar(planner, int(perfil), apelido, self._blizzard)
        except ErroMaxroll as e:
            return {"erro": str(e)}
        problemas = problemas_da_build(build)
        if problemas:  # não devia acontecer; se acontecer, não grava build quebrada
            return {"erro": "A build veio com problema: " + " ".join(problemas)}
        return {"id": salvar_build(build).stem}

    def abrir_link(self, url: str) -> None:
        """Abre o guia da build no navegador do Windows (não dentro da janela).
        Só links do Maxroll: o endereço vem do arquivo da build."""
        if isinstance(url, str) and url.startswith("https://maxroll.gg/"):
            webbrowser.open(url)

    def problemas_das_builds(self) -> dict[str, list[str]]:
        """{arquivo: [o que corrigir]} das builds que ficaram de fora."""
        return ler_builds()[1]

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

    def escolher_build(self, id_build: str) -> dict:
        """Build que o F8 usa ("" = todas). Não reinicia o overlay: ele relê a
        escolha a cada F8."""
        return {"erros": salvar_config({"BUILD_ATIVA": id_build})}

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
