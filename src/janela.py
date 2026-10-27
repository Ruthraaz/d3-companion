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
import json
import os
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
from heroi import comparar, herois, heroi
from maxroll import (ErroMaxroll, baixar_planner, builds_do_heroi, catalogo, classe_do_planner,
                     link_de_guia, montar, nomes_dos_perfis, planners_do_link, regravar_build,
                     remover_build, salvar_build)
from link_do_site import ErroLinkDoSite, build_do_link, build_montada, e_link_do_site
from nucleo import PASTA_CAPTURAS, dica_do_mistico
from pastas import NO_EXE, WEB
from rede import link_seguro

PASTA_SRC = Path(__file__).resolve().parent
PAGINA = WEB / "index.html"
ICONE_DE_ITEM = "https://blzmedia-a.akamaihd.net/d3/icons/items/large/{}.png"
LARGURA_MINIATURA = 220
SITE_DO_APP = "https://ruthraaz.github.io/d3-companion/"
MAXIMO_DA_BUILD = 200_000  # caracteres do JSON de uma build montada (como no link do site)


class Overlay:
    """O processo do overlay (src/app.py): liga, desliga e guarda o que ele imprime."""

    def __init__(self):
        self._processo: subprocess.Popen | None = None
        self.log: deque[str] = deque(maxlen=200)

    def ligar(self):
        self.desligar()
        self.log.clear()
        # No .exe o mesmo programa faz o overlay (--overlay); do código, é o app.py.
        comando = [sys.executable, "--overlay"] if NO_EXE else [sys.executable, "-u", str(PASTA_SRC / "app.py")]
        self._processo = subprocess.Popen(
            comando,  # -u: log na hora, sem buffer
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=os.environ | {"D3_JANELA_PID": str(os.getpid())},  # o overlay fecha se a janela sumir
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

    def guias(self, atualizar: bool = False) -> dict:
        """Todos os guias de classe do Maxroll (só a lista; as builds de um guia
        vêm quando ele é aberto, por buscar_maxroll). {"guias"} ou {"erro"}."""
        try:
            return {"guias": catalogo(atualizar=bool(atualizar))}
        except ErroMaxroll as e:
            return {"erro": str(e)}

    def buscar_maxroll(self, texto: str) -> dict:
        """Link de guia ou de planner do Maxroll -> builds que ele traz, com os
        perfis de cada uma. As do seguidor e as de outra classe ficam de fora.
        Link do "Montar build" do site -> {"site": {nome, apelido, classe}}."""
        if e_link_do_site(texto):
            try:
                build = build_do_link(texto)
            except ErroLinkDoSite as e:
                return {"erro": str(e)}
            return {"site": {"nome": build["nome"], "apelido": build["apelido"], "classe": build["classe"]}}
        try:
            planners = [baixar_planner(n) for n in planners_do_link(texto)]
        except ErroMaxroll as e:
            return {"erro": str(e)}
        herois = builds_do_heroi(planners, texto)
        for p in herois:
            p["_guia"] = link_de_guia(texto)  # a janela marca o guia como "já importado"
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

    def importar_do_site(self, texto: str, apelido: str = "") -> dict:
        """Grava em builds/ a build do link do site (nunca sobrescreve). {"id"} ou {"erro"}."""
        try:
            build = build_do_link(texto)
        except ErroLinkDoSite as e:
            return {"erro": str(e)}
        if isinstance(apelido, str) and apelido.strip():
            build["apelido"] = apelido.strip()[:40]
        return {"id": salvar_build(build).stem}

    # ------------------------------------------------------------ Montar build

    def dados_do_jogo(self, qual: str = "jogo") -> dict:
        """dados/jogo.json (o que o montador oferece), dados/dicas.json e
        dicas.en.json (o que cada item faz) ou dados/en.json (as frases da janela em
        inglês). Vêm junto com o app, gerados por ferramentas/dados_do_site.py."""
        if qual not in ("jogo", "dicas", "dicas.en", "en"):
            return {"erro": "Não sei que dados são esses."}
        try:
            return json.loads((WEB / "dados" / f"{qual}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"erro": f"Falta o arquivo dados/{qual}.json do app."}

    def salvar_montada(self, build: dict, id_build: str = "") -> dict:
        """Grava a build da aba Montar. Sem id cria uma nova (nunca sobrescreve);
        com id altera essa, se ela também foi feita no montador. {"id"} ou {"erro"}."""
        try:
            if len(json.dumps(build, ensure_ascii=False)) > MAXIMO_DA_BUILD:
                return {"erro": "Essa build está grande demais."}
            build = build_montada(build)
        except (ErroLinkDoSite, TypeError, ValueError) as e:
            return {"erro": str(e)}
        if id_build:
            arquivo = regravar_build(id_build, build)
            if arquivo is None:
                return {"erro": "Não achei essa build pra alterar (só as feitas no montador podem ser alteradas)."}
            return {"id": arquivo.stem}
        return {"id": salvar_build(build).stem}

    def build_para_montar(self, id_build: str) -> dict:
        """A build inteira, pra abrir na aba Montar. pode_alterar: se "Salvar
        mudanças" grava em cima dela (só as feitas no montador)."""
        build = next((b for b in ler_builds()[0] if b["id"] == id_build), None)
        if build is None:
            return {"erro": f"Build {id_build!r} não encontrada."}
        return {"build": {k: v for k, v in build.items() if k != "id"},
                "pode_alterar": (build.get("fonte") or {}).get("site") == "montar"}

    def remover_build(self, id_build: str) -> dict:
        """Tira a build do app (apaga o arquivo dela em builds/). Se era a do
        atalho, o atalho volta a usar todas. {"ok"} ou {"erro"}."""
        if not remover_build(str(id_build)):
            return {"erro": "Essa build não está mais na pasta."}
        if ler_config().get("BUILD_ATIVA") == id_build:
            salvar_config({"BUILD_ATIVA": ""})
        self._overlay.ligar()  # o overlay só lê builds/ ao abrir
        return {"ok": True}

    def abrir_link(self, url: str) -> None:
        """Abre o guia da build no navegador do Windows (não dentro da janela).
        Só links do Maxroll: o endereço vem do arquivo da build (que pode ter
        sido editado à mão), então confere tudo antes de passar pro Windows."""
        if link_seguro(url):
            webbrowser.open(url)

    def abrir_site(self) -> None:
        """Abre o site do app no navegador (endereço fixo, nada vem da página)."""
        webbrowser.open(SITE_DO_APP)

    def herois(self, battletag: str) -> dict:
        """Heróis da conta (API de perfil da Blizzard). Guarda a BattleTag no .env
        pra não precisar digitar de novo. {"herois"} ou {"erro"}."""
        try:
            lista = herois(self._blizzard, battletag)
        except ErroBlizzard as e:
            return {"erro": str(e)}
        salvar_config({"BATTLETAG": battletag.strip()})
        return {"herois": lista}

    def comparar_heroi(self, battletag: str, id_heroi: int, id_build: str) -> dict:
        """O herói contra uma build: item por item (o mesmo avaliador do F8) e
        as habilidades, já com os nomes em português."""
        build = next((b for b in ler_builds()[0] if b["id"] == id_build), None)
        if build is None:
            return {"erro": f"Build {id_build!r} não encontrada."}
        try:
            h = heroi(self._blizzard, battletag, int(id_heroi))
            r = comparar(h, build)
        except ErroBlizzard as e:
            return {"erro": str(e)}
        itens = []
        for x in r["itens"]:
            res = x["resultado"]
            itens.append({
                "espaco": x["espaco"],
                "nome": x["item"]["nome"],
                "qualidade": x["item"]["qualidade"],
                "icone": ICONE_DE_ITEM.format(x["item"]["icone"]) if x["item"].get("icone") else None,
                "veredito": "serve" if res["bate"] else "parcial" if res["por_enquanto"] else "nao",
                "motivo": res["motivo"],
                "tem": [a["rotulo"] for a in res["afixos"] if a["ok"]],
                "falta": [a["rotulo"] for a in res["afixos"] if not a["ok"]],
                "dica": dica_do_mistico(res),
                "encantado": x["item"].get("encantado"),
            })
        nomes, runas = {}, {}
        try:  # nomes em português; sem eles, ficam os códigos
            da_classe = self._blizzard.habilidades(build["classe"])
            nomes = {h["slug"]: h for tipo in ("ativas", "passivas") for h in da_classe[tipo]}
            for a in r["habilidades"]["ativas"]:
                if a["habilidade"] in nomes:
                    runas[a["habilidade"]] = {x["letra"]: x["nome_pt"]
                                              for x in self._blizzard.runas(build["classe"], a["habilidade"])}
        except ErroBlizzard:
            pass
        def nome(slug):
            return nomes.get(slug, {}).get("nome_pt", slug)
        def icone(slug):
            return nomes.get(slug, {}).get("icone")
        hab = r["habilidades"]
        return {
            "heroi": {k: h[k] for k in ("nome", "classe", "nivel", "paragon", "atualizado")},
            "classe_igual": r["classe_igual"],
            "itens": itens,
            "habilidades": {
                "ativas": [a | {"nome": nome(a["habilidade"]), "icone": icone(a["habilidade"]),
                                "runa_nome": runas.get(a["habilidade"], {}).get(a["runa"], ""),
                                "runa_do_heroi_nome": runas.get(a["habilidade"], {}).get(a["runa_do_heroi"] or "", "")}
                           for a in hab["ativas"]],
                "passivas": [p | {"nome": nome(p["habilidade"]), "icone": icone(p["habilidade"])} for p in hab["passivas"]],
                "fora_da_build": [nome(s) for s in hab["fora_da_build"]],
            },
        }

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
        width=1180, height=780, min_size=(900, 600), background_color="#111215",
    )
    janela.events.closed += overlay.desligar
    webview.start()
    overlay.desligar()


if __name__ == "__main__":
    main()
