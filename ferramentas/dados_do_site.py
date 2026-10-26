"""
Gera docs/dados/jogo.json: o que o "Montar build" do site oferece pra escolher.

    .venv\\Scripts\\activate
    python ferramentas/dados_do_site.py

Vem da API oficial da Blizzard (com a sua chave do .env, aqui no seu PC; a chave
nunca vai pro site) e usa o cache de dados/blizzard/. No arquivo só entram nomes,
códigos de ícone e níveis: as imagens continuam vindo do servidor da Blizzard.

  - itens lendários e de set por espaço (com a classe, quando o tipo é de uma só);
  - gemas lendárias;
  - habilidades, runas e passivas de cada classe, com o nome em português;
  - os afixos, no mesmo formato de regra que o app usa ao importar do Maxroll.

Rode de novo quando sair temporada nova (itens novos).
"""

import datetime
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from blizzard import CLASSES, Blizzard  # noqa: E402
from maxroll import CLASSES as CLASSES_MX  # noqa: E402
from maxroll import dados_do_planejador, regras_do_item  # noqa: E402

DESTINO = RAIZ / "docs" / "dados" / "jogo.json"

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


def copiar_css():
    """O site usa o mesmo CSS do app: docs/app.css é cópia do src/web/estilo.css."""
    (RAIZ / "docs" / "app.css").write_bytes((RAIZ / "src" / "web" / "estilo.css").read_bytes())
    print("docs/app.css atualizado.")


def main():
    copiar_css()
    if "--so-css" in sys.argv:
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
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(jogo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(len(v) for v in por_espaco.values())
    print(f"Pronto: {DESTINO.relative_to(RAIZ)} ({DESTINO.stat().st_size // 1024} KB, "
          f"{total} itens, {len(gemas)} gemas, {len(jogo['afixos'])} afixos)")


if __name__ == "__main__":
    main()
