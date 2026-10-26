"""
Gera os dados do jogo do "Montar build" (app e site) e das dicas de item:

    src/web/dados/jogo.json   o que o montador oferece pra escolher
    src/web/dados/dicas.json  o que cada item e gema faz (aparece ao passar o mouse)

e copia pro site (docs/) esses dados e os arquivos que o site usa iguais ao app
(o CSS, o montador e a dica). Um teste confere que as cópias estão em dia.

    .venv\\Scripts\\activate
    python ferramentas/dados_do_site.py

Vem da API oficial da Blizzard (com a sua chave do .env, aqui no seu PC; a chave
nunca vai pro site) e usa o cache de dados/blizzard/. No arquivo só entram nomes,
códigos de ícone e níveis: as imagens continuam vindo do servidor da Blizzard.

  - itens lendários e de set por espaço (com a classe, quando o tipo é de uma só);
  - gemas lendárias;
  - habilidades, runas e passivas de cada classe, com o nome em português;
  - os afixos, no mesmo formato de regra que o app usa ao importar do Maxroll;
  - nas dicas: nome e tipo em português, o poder lendário e os bônus do set,
    só como texto (o HTML da Blizzard é lido aqui e nunca vai pra tela).

Rode de novo quando sair temporada nova (itens novos). Só copiar (sem API):

    python ferramentas/dados_do_site.py --so-copiar
"""

import datetime
import html.parser
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from blizzard import CLASSES, Blizzard  # noqa: E402
from maxroll import CLASSES as CLASSES_MX  # noqa: E402
from maxroll import dados_do_planejador, regras_do_item  # noqa: E402

DADOS = RAIZ / "src" / "web" / "dados"
# Arquivo do app -> cópia no site.
COPIAS = {
    RAIZ / "src" / "web" / "estilo.css": RAIZ / "docs" / "app.css",
    RAIZ / "src" / "web" / "montar.css": RAIZ / "docs" / "montar.css",
    RAIZ / "src" / "web" / "montar.js": RAIZ / "docs" / "montar.js",
    RAIZ / "src" / "web" / "dica.js": RAIZ / "docs" / "dica.js",
    DADOS / "jogo.json": RAIZ / "docs" / "dados" / "jogo.json",
    DADOS / "dicas.json": RAIZ / "docs" / "dados" / "dicas.json",
}

# Tipo de item da Blizzard (id em minúsculas) -> espaço da build.
ESPACO_DO_TIPO = {
    "helm": "Head", "generichelm": "Head", "spiritstone_monk": "Head", "voodoomask": "Head", "wizardhat": "Head",
    "shoulders": "Shoulders", "chestarmor": "Torso", "genericchestarmor": "Torso", "cloak": "Torso",
    "gloves": "Hands", "bracers": "Wrists", "genericbelt": "Waist", "belt_barbarian": "Waist",
    "legs": "Legs", "boots": "Feet", "amulet": "Neck", "ring": "Finger",
    "shield": "Off-Hand", "crusadershield": "Off-Hand", "quiver": "Off-Hand", "mojo": "Off-Hand",
    "orb": "Off-Hand", "necromanceroffhand": "Off-Hand",
}
ARMAS_1M = {"axe", "sword", "mace", "dagger", "spear", "fistweapon", "mightyweapon1h", "flail1h",
            "ceremonialdagger", "wand", "scythe1h", "handxbow"}
ARMAS_2M = {"axe2h", "sword2h", "mace2h", "polearm", "staff", "combatstaff", "mightyweapon2h", "flail2h",
            "scythe2h", "bow", "crossbow"}
# Tipos que só uma classe usa (os "_Classe" já dizem no nome).
CLASSE_DO_TIPO = {
    "handxbow": "Demon Hunter", "quiver": "Demon Hunter", "cloak": "Demon Hunter",
    "spiritstone_monk": "Monk", "fistweapon": "Monk", "combatstaff": "Monk",
    "mightyweapon1h": "Barbarian", "mightyweapon2h": "Barbarian", "belt_barbarian": "Barbarian",
    "flail1h": "Crusader", "flail2h": "Crusader", "crusadershield": "Crusader",
    "voodoomask": "Witch Doctor", "mojo": "Witch Doctor", "ceremonialdagger": "Witch Doctor",
    "wizardhat": "Wizard", "orb": "Wizard", "wand": "Wizard",
    "scythe1h": "Necromancer", "scythe2h": "Necromancer", "necromanceroffhand": "Necromancer",
}
SUFIXO_DA_CLASSE = {"_barbarian": "Barbarian", "_crusader": "Crusader", "_demonhunter": "Demon Hunter",
                    "_monk": "Monk", "_necromancer": "Necromancer", "_witchdoctor": "Witch Doctor",
                    "_wizard": "Wizard"}
GEMAS = "upgradeablejewel"

# Afixos que o site oferece (chaves do Maxroll), na ordem da lista.
AFIXOS = ["sockets", "chc", "chd", "vit", "area", "ias", "cdr", "rcr", "resall", "life", "armor", "lph",
          "regen", "dmgred", "edmg", "edef", "damage", "ms",
          "dmgphy", "dmgfir", "dmgcol", "dmglit", "dmgpsn", "dmgarc", "dmghol"]


def espaco_e_classe(tipo_id: str) -> tuple[str | None, str | None, bool]:
    """"Helm_Crusader" -> ("Head", "Crusader", False); "Bow" -> ("Weapon", None, True)."""
    tipo = tipo_id.lower()
    classe = None
    for sufixo, cl in SUFIXO_DA_CLASSE.items():
        if tipo.endswith(sufixo) and tipo != "spiritstone_monk":
            tipo, classe = tipo[: -len(sufixo)], cl
    classe = classe or CLASSE_DO_TIPO.get(tipo_id.lower())
    if tipo in ARMAS_1M:
        return "Weapon", classe, False
    if tipo in ARMAS_2M:
        return "Weapon", classe, True
    return ESPACO_DO_TIPO.get(tipo), classe, False


def itens(api: Blizzard) -> tuple[dict, list]:
    espacos, gemas = {}, {}
    for tipo in api.pegar("/d3/data/item-type"):
        espaco, classe, duas_maos = espaco_e_classe(tipo["id"])
        e_gema = tipo["id"].lower() == GEMAS
        if not espaco and not e_gema:
            continue
        for item in api.pegar("/d3/data/" + tipo["path"]):
            if "unique" not in item["id"].lower():
                continue  # só lendário e set: o resto ninguém põe em build
            if e_gema:
                gemas.setdefault(item["name"], item["icon"])
                continue
            lista = espacos.setdefault(espaco, {})
            atual = lista.get(item["name"])
            classes = {classe} if classe else set()
            if atual:  # mesmo item em tipos de mais de uma classe: junta
                atual["c"] = sorted(set(atual["c"]) | classes) if atual["c"] and classes else []
                continue
            lista[item["name"]] = {"n": item["name"], "i": item["icon"], "c": sorted(classes),
                                   **({"s": 1} if "_set_" in item["id"].lower() else {}),
                                   **({"m2": 1} if duas_maos else {})}
    return ({e: sorted(v.values(), key=lambda x: x["n"]) for e, v in espacos.items()},
            [{"n": n, "i": i} for n, i in sorted(gemas.items())])


def classes(api: Blizzard, dados: dict) -> dict:
    resultado = {}
    for classe_mx, (classe, atributo, rotulo, _) in CLASSES_MX.items():
        hab = api.habilidades(classe)
        ativas = []
        for h in hab["ativas"]:
            runas = api.runas(classe, h["slug"])
            ativas.append({"s": h["slug"], "n": h["nome"], "p": h["nome_pt"], "i": h["icone"].rsplit("/", 1)[-1][:-4],
                           "l": h["nivel"], "r": [[r["letra"], r["nome_pt"], r["nivel"]] for r in runas]})
        passivas = [{"s": h["slug"], "n": h["nome"], "p": h["nome_pt"], "i": h["icone"].rsplit("/", 1)[-1][:-4],
                     "l": h["nivel"]} for h in hab["passivas"]]
        da_classe = regras_do_item({f"damage_{classe_mx}": {}}, dados, "", {})
        resultado[classe] = {"atributo": {"modelo": f"+# {atributo}", "rotulo": rotulo},
                             "afixo": da_classe[0] if da_classe else None,
                             "ativas": ativas, "passivas": passivas}
        print(f"  {classe}: {len(ativas)} habilidades, {len(passivas)} passivas")
    return resultado


def afixos(dados: dict) -> list[dict]:
    lista = []
    for chave in AFIXOS:
        lista += regras_do_item({chave: {}}, dados, "", {})
    return lista


# ------------------------------------------------------------ dicas

# Cores da Blizzard no HTML do item.
LARANJA, CINZA, VERMELHO, VERDE = "d3-color-ffff8000", "d3-color-ff9b9b9b", "d3-color-ffff0000", "d3-color-ff00ff00"
AZUL = "d3-color-ff6969ff"


class _Trechos(html.parser.HTMLParser):
    """HTML da Blizzard -> [(cor, texto)]: cada <span> de cor de fora vira um
    trecho, com o texto de dentro dele. Só texto sai daqui (nenhuma tag)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.trechos, self._pilha = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "span":
            cor = next((c for c in (dict(attrs).get("class") or "").split() if c.startswith("d3-color-")), None)
            if cor and not any(self._pilha):
                self.trechos.append([cor, ""])
            self._pilha.append(cor)
        elif tag == "br" and any(self._pilha):
            self.trechos[-1][1] += "\n"

    def handle_endtag(self, tag):
        if tag == "span" and self._pilha:
            self._pilha.pop()

    def handle_data(self, dados):
        if any(self._pilha):
            self.trechos[-1][1] += dados


def trechos(texto_html: str) -> list[tuple[str, str]]:
    leitor = _Trechos()
    leitor.feed(texto_html or "")
    return [(cor, re.sub(r"[ \t]+", " ", t).strip()) for cor, t in leitor.trechos if t.strip()]


def poderes(item: dict, e_gema: bool) -> list[str]:
    """As linhas laranja (poder lendário). No item, a faixa do valor (cinza) vai
    junto; na gema o cinza só repete o valor e fica de fora."""
    linhas = []
    for linha in ((item.get("attributes") or {}).get("secondary") or []):
        partes = trechos(linha.get("textHtml", ""))
        poder = " ".join(t for c, t in partes if c == LARANJA)
        if not poder:
            continue
        faixa = next((t for c, t in partes if c == CINZA), "")
        so = next((t.strip("()") for c, t in partes if c == VERMELHO), "")
        linhas.append(poder + (f" (no jogo: {faixa})" if faixa and not e_gema else "") + (f" · {so}" if so else ""))
    if not linhas:  # alguns poderes vêm em azul, como afixo fixo (ex.: Ring of Royal Grandeur)
        for linha in ((item.get("attributes") or {}).get("secondary") or []):
            texto = " ".join(t for c, t in trechos(linha.get("textHtml", "")) if c == AZUL)
            if texto and not texto.startswith("Engaste"):
                linhas.append(texto)
    return linhas


def bonus_do_set(item: dict) -> list[str]:
    """"Conjunto (2): ..." de cada bônus, numa linha só cada."""
    return [re.sub(r"\s*\n\s*", " ", t) for c, t in trechos(item.get("setDescriptionHtml") or "") if c == VERDE]


def dica(api: Blizzard, nome: str, e_gema: bool):
    """(nome, dica, (set, bônus) ou None), ou None se a Blizzard não conhece o item."""
    achado = api.item(nome)
    if not achado:
        return None
    item = api.pegar("/d3/data/" + achado["caminho"], locale="pt_BR")
    d = {"n": item.get("name") or nome, "t": item.get("typeName") or ""}
    poder = poderes(item, e_gema)
    if poder:
        d["p"] = poder
    elif not item.get("setName") and item.get("flavorText"):
        d["f"] = item["flavorText"][:300]  # sem poder: ao menos o texto do item
    conjunto = None
    if item.get("setName"):
        d["s"] = item["setName"]
        conjunto = (item["setName"], bonus_do_set(item))
    return nome, d, conjunto


def dicas(api: Blizzard, por_espaco: dict, gemas: list) -> dict:
    nomes = sorted({i["n"] for lista in por_espaco.values() for i in lista})
    pedidos = [(n, False) for n in nomes] + [(g["n"], True) for g in gemas]
    api._token_valido()  # um token só, antes das threads
    with ThreadPoolExecutor(max_workers=8) as grupo:
        achados = [r for r in grupo.map(lambda p: dica(api, *p), pedidos) if r]
    resultado = {"itens": {}, "sets": {}}
    for nome, d, conjunto in achados:
        resultado["itens"][nome] = d
        if conjunto and conjunto[1]:
            resultado["sets"][conjunto[0]] = conjunto[1]
    return resultado


# ------------------------------------------------------------ gravar e copiar

def copiar():
    """O site usa os mesmos arquivos do app: copia pra docs/."""
    for origem, destino in COPIAS.items():
        if origem.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origem, destino)
    print("Cópias do site (docs/) atualizadas.")


def gravar(nome: str, dados: dict) -> Path:
    DADOS.mkdir(parents=True, exist_ok=True)
    arquivo = DADOS / nome
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return arquivo


def main():
    if "--so-copiar" in sys.argv:
        copiar()
        return
    api = Blizzard()
    dados = dados_do_planejador()
    print("Itens e gemas…")
    por_espaco, gemas = itens(api)
    print("Classes…")
    jogo = {
        "versao": 1,
        "gerado": datetime.date.today().isoformat(),
        "fonte": "API oficial da Blizzard (nomes e códigos de ícone; as imagens vêm do servidor dela)",
        "classes": classes(api, dados),
        "espacos": por_espaco,
        "gemas": gemas,
        "afixos": afixos(dados),
    }
    arquivo = gravar("jogo.json", jogo)
    total = sum(len(v) for v in por_espaco.values())
    print(f"Pronto: {arquivo.relative_to(RAIZ)} ({arquivo.stat().st_size // 1024} KB, "
          f"{total} itens, {len(gemas)} gemas, {len(jogo['afixos'])} afixos)")
    print("Dicas (o que cada item faz; na 1ª vez são ~840 pedidos)…")
    arquivo = gravar("dicas.json", {"versao": 1, "gerado": jogo["gerado"], "fonte": jogo["fonte"]}
                     | dicas(api, por_espaco, gemas))
    print(f"Pronto: {arquivo.relative_to(RAIZ)} ({arquivo.stat().st_size // 1024} KB)")
    copiar()


if __name__ == "__main__":
    main()
