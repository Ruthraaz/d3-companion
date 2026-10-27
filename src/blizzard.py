"""
Dados oficiais do Diablo 3 pela API da Blizzard: habilidades, itens e ícones.

Chaves: BLIZZARD_CLIENT_ID e BLIZZARD_CLIENT_SECRET no .env (criadas em
https://develop.battle.net → API Access → Create Client). Elas nunca saem
do .env e nunca vão pro Git.

Como funciona:
  - pede um "token" à Blizzard com as chaves (vale 24 h, guardado na memória);
  - cada resposta da API é guardada em dados/blizzard/ (fora do Git). Os dados
    do jogo quase nunca mudam, então a segunda vez é instantânea e sem internet;
  - os ícones NÃO são baixados: guardamos só o endereço da imagem no servidor
    da Blizzard, e a janela carrega de lá na hora de mostrar.

Os nomes ficam em inglês (é como o jogo e o OCR mostram, e como as builds
estão escritas); nome e descrição em português vêm junto pra mostrar na tela.

Uso:
    python src/blizzard.py              # testa as chaves e confere os itens das builds
    python src/blizzard.py --atualizar  # apaga o cache e busca tudo de novo
"""

import base64
import json
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import dotenv_values

from idioma import t
from pastas import ARQUIVO_ENV, PASTA_DADOS
from rede import RespostaGrande, ler

PASTA_CACHE = PASTA_DADOS / "blizzard"

URL_TOKEN = "https://oauth.battle.net/token"
URL_API = "https://us.api.blizzard.com"  # Américas (o Brasil joga nesta região)
URL_ICONES = "https://blzmedia-a.akamaihd.net/d3/icons"

# Nome da classe nas builds -> slug da API
CLASSES = {
    "Barbarian": "barbarian",
    "Crusader": "crusader",
    "Demon Hunter": "demon-hunter",
    "Monk": "monk",
    "Necromancer": "necromancer",
    "Witch Doctor": "witch-doctor",
    "Wizard": "wizard",
}


SEGUIDORES = ("templar", "scoundrel", "enchantress")


class ErroBlizzard(Exception):
    """Erro com mensagem em português, pronta pra mostrar na tela."""


def icone_da_habilidade(icone: str, tamanho: int = 64) -> str:
    return f"{URL_ICONES}/skills/{tamanho}/{icone}.png"


def icone_do_item(icone: str, tamanho: str = "large") -> str:
    return f"{URL_ICONES}/items/{tamanho}/{icone}.png"


def chave_do_nome(nome: str) -> str:
    """Nome normalizado pra comparar: sem acento, sem maiúscula, apóstrofo
    curvo = reto, espaços juntos. "Yang’s  Recurve" == "yang's recurve"."""
    nome = nome.replace("’", "'").replace("‘", "'")  # antes de tirar acento, senão o ’ some
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", nome).strip()


class Blizzard:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 pasta_cache: Path = PASTA_CACHE, abrir=urllib.request.urlopen):
        if client_id is None or client_secret is None:
            env = dotenv_values(ARQUIVO_ENV) if ARQUIVO_ENV.exists() else {}
            client_id = client_id or env.get("BLIZZARD_CLIENT_ID")
            client_secret = client_secret or env.get("BLIZZARD_CLIENT_SECRET")
        self._id = (client_id or "").strip()
        self._segredo = (client_secret or "").strip()
        self.pasta_cache = pasta_cache
        self._abrir = abrir  # trocado nos testes, pra não usar a internet
        self._token = None
        self._token_vence = 0.0

    # ------------------------------------------------------------ conexão

    def _token_valido(self) -> str:
        if self._token and time.time() < self._token_vence:
            return self._token
        if not self._id or not self._segredo:
            raise ErroBlizzard(t("Esta parte precisa de uma chave grátis da Blizzard. O LEIA-ME.txt, na pasta do app, "
                                 "mostra como criar em develop.battle.net e onde colocar "
                                 "(BLIZZARD_CLIENT_ID e BLIZZARD_CLIENT_SECRET no .env)."))
        cred = base64.b64encode(f"{self._id}:{self._segredo}".encode()).decode()
        pedido = urllib.request.Request(
            URL_TOKEN, data=b"grant_type=client_credentials",
            headers={"Authorization": "Basic " + cred,
                     "Content-Type": "application/x-www-form-urlencoded"})
        try:
            resposta = self._ler(pedido)
        except urllib.error.HTTPError as e:
            if e.code in (400, 401):
                raise ErroBlizzard(t("A Blizzard recusou as chaves. Confira BLIZZARD_CLIENT_ID e "
                                     "BLIZZARD_CLIENT_SECRET no .env (sem aspas nem espaços).")) from e
            raise ErroBlizzard(t("A Blizzard respondeu com erro {codigo} ao pedir o token.", codigo=e.code)) from e
        self._token = resposta["access_token"]
        self._token_vence = time.time() + resposta.get("expires_in", 3600) - 60
        return self._token

    def _ler(self, pedido) -> dict | list:
        try:
            with self._abrir(pedido, timeout=20) as r:
                return json.loads(ler(r))
        except urllib.error.HTTPError:
            raise
        except RespostaGrande as e:
            raise ErroBlizzard(t("A Blizzard mandou uma resposta grande demais; o app não abriu.")) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErroBlizzard(t("Não consegui falar com a Blizzard. Está sem internet?")) from e

    def _arquivo_do_cache(self, caminho: str, locale: str) -> Path:
        nome = re.sub(r"[^A-Za-z0-9_.-]+", "_", caminho.strip("/"))
        return self.pasta_cache / locale / f"{nome}.json"

    def pegar(self, caminho: str, locale: str = "en_US", guardar: bool = True):
        """GET em /d3/... da API, com cache em disco (guardar=False: sempre da
        Blizzard e sem gravar; é o caso do perfil do herói, que muda)."""
        arquivo = self._arquivo_do_cache(caminho, locale)
        if guardar and arquivo.exists():
            return json.loads(arquivo.read_text(encoding="utf-8"))
        url = f"{URL_API}{caminho}?{urllib.parse.urlencode({'locale': locale})}"
        pedido = urllib.request.Request(url, headers={"Authorization": "Bearer " + self._token_valido()})
        try:
            dados = self._ler(pedido)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ErroBlizzard(t("A Blizzard não conhece {caminho}.", caminho=repr(caminho))) from e
            raise ErroBlizzard(t("A Blizzard respondeu com erro {codigo} em {caminho}.",
                                 codigo=e.code, caminho=repr(caminho))) from e
        if not guardar:
            return dados
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return dados

    def apagar_cache(self):
        shutil.rmtree(self.pasta_cache, ignore_errors=True)

    # ------------------------------------------------------------ habilidades

    def habilidades(self, classe: str) -> dict:
        """{"ativas": [...], "passivas": [...]} da classe ("Demon Hunter").

        Cada habilidade: slug, nome (inglês, como no jogo), nome_pt, nivel,
        icone (endereço da imagem), descricao (inglês) e descricao_pt.
        """
        if classe not in CLASSES:
            raise ErroBlizzard(f"Classe {classe!r} não existe. Opções: {', '.join(CLASSES)}.")
        caminho = f"/d3/data/hero/{CLASSES[classe]}"
        en, pt = self.pegar(caminho, "en_US"), self.pegar(caminho, "pt_BR")
        resultado = {}
        for tipo, chave in (("ativas", "active"), ("passivas", "passive")):
            em_pt = {h["slug"]: h for h in pt["skills"][chave]}
            resultado[tipo] = [{
                "slug": h["slug"],
                "nome": h["name"],
                "nome_pt": em_pt.get(h["slug"], h)["name"],
                "nivel": h.get("level"),
                "icone": icone_da_habilidade(h["icon"]),
                "descricao": h.get("description", ""),
                "descricao_pt": em_pt.get(h["slug"], h).get("description", ""),
            } for h in en["skills"][chave]]
        return resultado

    def runas(self, classe: str, slug: str) -> list[dict]:
        """As 5 runas de uma habilidade ativa: letra (a-e, como a build guarda),
        slug, nome, nome_pt, descricao, descricao_pt e nivel (em que nível do herói libera)."""
        caminho = f"/d3/data/hero/{CLASSES[classe]}/skill/{slug}"
        en, pt = self.pegar(caminho, "en_US"), self.pegar(caminho, "pt_BR")
        em_pt = {r["type"]: r for r in pt.get("runes", [])}
        return [{"letra": r["type"], "slug": r["slug"], "nome": r["name"],
                 "nome_pt": em_pt.get(r["type"], r)["name"],
                 "descricao": r.get("description", ""),
                 "descricao_pt": em_pt.get(r["type"], r).get("description", ""),
                 "nivel": r.get("level")}
                for r in en.get("runes", [])]

    def seguidor(self, quem: str) -> dict:
        """O seguidor ("templar"): nome_pt e as habilidades (slug, nome, nome_pt,
        nivel, icone, descricao, descricao_pt, codigo = nome do ícone, igual ao código do Maxroll)."""
        if quem not in SEGUIDORES:
            raise ErroBlizzard(f"Seguidor {quem!r} não existe. Opções: {', '.join(SEGUIDORES)}.")
        caminho = f"/d3/data/follower/{quem}"
        en, pt = self.pegar(caminho, "en_US"), self.pegar(caminho, "pt_BR")
        em_pt = {h["slug"]: h for h in pt.get("skills", [])}
        return {"quem": quem, "nome": en.get("name"), "nome_pt": pt.get("name") or en.get("name"),
                "habilidades": [{
                    "slug": h["slug"], "codigo": h.get("icon", ""),
                    "nome": h["name"], "nome_pt": em_pt.get(h["slug"], h)["name"],
                    "nivel": h.get("level"), "icone": icone_da_habilidade(h["icon"]),
                    "descricao": h.get("description", ""),
                    "descricao_pt": em_pt.get(h["slug"], h).get("description", ""),
                } for h in en.get("skills", [])]}

    # ------------------------------------------------------------ itens

    def indice_de_itens(self) -> dict[str, dict]:
        """Todos os itens do jogo por nome (chave_do_nome) -> id, nome, tipo,
        icone e caminho na API. Na primeira vez são ~135 pedidos (um por tipo
        de item, ~20 s); depois vem do cache."""
        arquivo = self.pasta_cache / "indice_de_itens.json"
        if arquivo.exists():
            return json.loads(arquivo.read_text(encoding="utf-8"))
        tipos = [t["path"] for t in self.pegar("/d3/data/item-type")]
        self._token_valido()  # um token só, antes de abrir as threads
        with ThreadPoolExecutor(max_workers=8) as grupo:
            listas = list(grupo.map(lambda t: (t, self.pegar("/d3/data/" + t)), tipos))
        indice = {}
        for tipo, itens in listas:
            for item in itens:
                chave = chave_do_nome(item["name"])
                # Mesmo nome em mais de um tipo: o lendário/set ("Unique" no id) ganha.
                if chave in indice and "unique" not in item["id"].lower():
                    continue
                indice[chave] = {"id": item["id"], "nome": item["name"], "tipo": tipo.split("/")[-1],
                                 "icone": icone_do_item(item["icon"]), "caminho": item["path"]}
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
        return indice

    def item(self, nome: str) -> dict | None:
        """O item pelo nome (como no jogo), ou None se a Blizzard não conhece."""
        return self.indice_de_itens().get(chave_do_nome(nome))

    def detalhes_do_item(self, nome: str) -> dict | None:
        """O item completo (atributos, set, etc.) pelo nome, ou None."""
        achado = self.item(nome)
        return self.pegar("/d3/data/" + achado["caminho"]) if achado else None


def visual_da_build(build: dict, api: "Blizzard") -> dict:
    """Ícones e textos em português pra janela mostrar a build:

      itens: {nome do item: {"nome", "icone"}} (espaços, cubo e gemas);
             item que a Blizzard não conhece fica com icone None;
      habilidades: {"ativas": [...], "passivas": [...]}, cada uma com nome,
             nome_pt, icone, descricao_pt e, nas ativas, a runa escolhida.
    """
    indice = api.indice_de_itens()
    nomes = [n for e in build.get("espacos", {}).values() for n in e.get("itens", [])]
    nomes += list(build.get("cubo", {}).values()) + build.get("gemas", [])
    nomes += list((build.get("seguidor") or {}).get("itens", {}).values())
    itens = {}
    for nome in nomes:
        achado = indice.get(chave_do_nome(nome))
        itens[nome] = {"nome": nome, "icone": achado["icone"] if achado else None}

    escolhidas = build.get("habilidades", {})
    habilidades = {"ativas": [], "passivas": []}
    if escolhidas.get("ativas") or escolhidas.get("passivas"):
        da_classe = api.habilidades(build["classe"])
        por_slug = {h["slug"]: h for tipo in ("ativas", "passivas") for h in da_classe[tipo]}
        for ativa in escolhidas.get("ativas", []):
            h = por_slug.get(ativa["habilidade"])
            if h is None:  # escrita errada na build: mostra o nome cru, sem ícone
                habilidades["ativas"].append({"slug": ativa["habilidade"], "nome": ativa["habilidade"],
                                              "nome_pt": ativa["habilidade"], "icone": None,
                                              "descricao_pt": "", "runa": None})
                continue
            runa = next((r for r in api.runas(build["classe"], h["slug"])
                         if r["letra"] == ativa.get("runa")), None)
            habilidades["ativas"].append(h | {"runa": runa})
        for slug in escolhidas.get("passivas", []):
            habilidades["passivas"].append(por_slug.get(slug) or {
                "slug": slug, "nome": slug, "nome_pt": slug, "icone": None, "descricao_pt": ""})
    return {"itens": itens, "habilidades": habilidades, "seguidor": _visual_do_seguidor(build, api)}


def _visual_do_seguidor(build: dict, api: "Blizzard") -> dict | None:
    """Nome em português e as habilidades escolhidas (na ordem do nível).
    A build guarda o slug ("guardian") ou o código do Maxroll ("templar_cheatdeath_passive")."""
    escolhido = build.get("seguidor")
    if not escolhido:
        return None
    try:
        dele = api.seguidor(escolhido["quem"])
    except ErroBlizzard:
        return None
    achar = {h["codigo"].lower(): h for h in dele["habilidades"]} | {h["slug"]: h for h in dele["habilidades"]}
    habilidades = [achar.get(s.lower()) or {"slug": s, "nome": s, "nome_pt": s, "nivel": None, "icone": None,
                                            "descricao_pt": ""}
                   for s in escolhido.get("habilidades", [])]
    habilidades.sort(key=lambda h: h["nivel"] or 99)
    return {"nome": dele["nome"], "nome_pt": dele["nome_pt"], "habilidades": habilidades}


def itens_desconhecidos(build: dict, indice: dict[str, dict]) -> list[str]:
    """Nomes de itens e gemas da build que a Blizzard não conhece (erro de
    digitação, quase sempre)."""
    nomes = [n for e in build.get("espacos", {}).values() for n in e.get("itens", [])]
    nomes += build.get("gemas", [])
    return [n for n in nomes if chave_do_nome(n) not in indice]


def _sugestao(nome: str, indice: dict[str, dict]) -> str:
    import difflib
    parecidos = difflib.get_close_matches(chave_do_nome(nome), list(indice), n=1, cutoff=0.75)
    return f" Quis dizer {indice[parecidos[0]]['nome']!r}?" if parecidos else ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    api = Blizzard()
    if "--atualizar" in sys.argv:
        api.apagar_cache()
        print("Cache apagado; buscando tudo de novo.")
    try:
        inicio = time.perf_counter()
        indice = api.indice_de_itens()
        print(f"✅ Chaves da Blizzard funcionando. {len(indice)} itens do jogo "
              f"({time.perf_counter() - inicio:.1f} s).")
        from avaliador import ler_builds
        builds, _ = ler_builds()
        for build in builds:
            hab = api.habilidades(build["classe"])
            faltando = itens_desconhecidos(build, indice)
            print(f"\n{build['nome']} ({build['classe']}): {len(hab['ativas'])} habilidades ativas, "
                  f"{len(hab['passivas'])} passivas.")
            if faltando:
                for nome in faltando:
                    print(f"   ❌ {nome!r}: a Blizzard não conhece esse nome.{_sugestao(nome, indice)}")
            else:
                print("   ✅ todos os itens e gemas da build existem no jogo.")
    except ErroBlizzard as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
