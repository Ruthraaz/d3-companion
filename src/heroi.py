"""
Seu herói de verdade (API de perfil da Blizzard) comparado com uma build.

Pela BattleTag (ex.: Jogador#1234), a Blizzard diz os heróis da conta e, de
cada um, os itens equipados e as habilidades. Cada item vira o mesmo formato
que o parser tira da dica do jogo, então o avaliador é o mesmo do F8.

Limites da API (da Blizzard, não do app):
  - só o que está EQUIPADO (mochila e baú continuam no F8);
  - atualiza quando você sai do jogo (ou troca de personagem), não na hora;
  - a conta precisa ser da região Américas (us), que é a do Brasil.

Uso:
    python src/heroi.py Jogador#1234                 # lista os heróis
    python src/heroi.py Jogador#1234 <id> <build>    # compara um herói com uma build (id do arquivo)
"""

import re
import sys
import urllib.parse

from avaliador import avaliar, carregar_builds
from blizzard import CLASSES, Blizzard, ErroBlizzard
from idioma import t
from parser import estruturar_afixo

# Lugar do item na API -> espaço nas builds. Os dois anéis usam o mesmo "Finger".
ESPACO_DO_PERFIL = {
    "head": "Head", "shoulders": "Shoulders", "neck": "Neck", "torso": "Torso",
    "hands": "Hands", "bracers": "Wrists", "waist": "Waist", "legs": "Legs",
    "feet": "Feet", "leftFinger": "Finger", "rightFinger": "Finger",
    "mainHand": "Weapon", "offHand": "Off-Hand",
}
CLASSE_DO_PERFIL = {slug: classe for classe, slug in CLASSES.items()}

QUALIDADE = re.compile(r"^((?:Primal )?(?:Ancient )?(?:Legendary|Set|Rare|Magic)?)\s*(.*)$")


def conta_da_battletag(texto: str) -> str:
    """"Jogador#1234" -> "Jogador-1234" (como a API quer). Erro claro se não parecer BattleTag.

    Nome só com letras (com acento) e números, como a Battle.net exige: assim "/",
    "." ou "?" nunca entram no endereço da API (não dá pra cair em outra página dela)."""
    m = re.fullmatch(r"\s*([^\W_]{2,12})\s*[#-]\s*(\d{3,6})\s*", texto or "")
    if not m:
        raise ErroBlizzard(t("Escreva a BattleTag com o número, ex.: Jogador#1234 "
                             "(aparece no canto do app da Battle.net)."))
    return f"{m.group(1)}-{m.group(2)}"


def _pegar(api: Blizzard, caminho: str) -> dict:
    try:
        return api.pegar(caminho, guardar=False)  # perfil muda: nunca do cache
    except ErroBlizzard as e:
        if "não conhece" in str(e):
            raise ErroBlizzard(t("A Blizzard não achou essa BattleTag na região Américas. "
                                 "Confira o número depois do #.")) from e
        raise


def herois(api: Blizzard, battletag: str) -> list[dict]:
    """Os heróis da conta, do jogado mais recente pro mais antigo."""
    conta = urllib.parse.quote(conta_da_battletag(battletag), safe="")
    perfil = _pegar(api, f"/d3/profile/{conta}/")
    lista = [{
        "id": h["id"],
        "nome": h["name"],
        "classe": CLASSE_DO_PERFIL.get(h.get("class")),
        "nivel": h.get("level"),
        "paragon": h.get("paragonLevel"),
        "temporada": bool(h.get("seasonal")),
        "hardcore": bool(h.get("hardcore")),
        "morto": bool(h.get("dead")),
        "atualizado": h.get("last-updated"),
    } for h in perfil.get("heroes", [])]
    return sorted(lista, key=lambda h: -(h["atualizado"] or 0))


def item_do_perfil(dados: dict, espaco: str) -> dict:
    """Item da API -> o mesmo formato do parser (o que o avaliador entende)."""
    qualidade, tipo = QUALIDADE.match(dados.get("typeName") or "").groups()
    atributos = dados.get("attributes") or {}
    html = (dados.get("attributesHtml") or {}).get("primary", [])
    primarios, encantado = [], None
    for i, texto in enumerate(atributos.get("primary", [])):
        if "Caldesann" in texto:  # aumento do cubo: não é afixo do item
            continue
        afixo = estruturar_afixo(texto)
        primarios.append(afixo)
        if i < len(html) and "tooltip-icon-enchant" in html[i]:
            encantado = afixo["texto"]  # trocado no Místico: só esse pode ser trocado de novo
    return {
        "nome": dados.get("name"),
        "qualidade": qualidade or "Normal",
        "tipo": tipo,
        "slot": espaco,
        "primarios": primarios,
        "secundarios": [estruturar_afixo(t) for t in atributos.get("secondary", [])],
        "soquetes": int(dados.get("openSockets") or 0) + len(dados.get("gems") or []),
        "encantado": encantado,
        "icone": dados.get("icon"),
    }


def heroi(api: Blizzard, battletag: str, id_heroi: int) -> dict:
    """Um herói com os itens equipados (por lugar da API) e as habilidades."""
    conta = urllib.parse.quote(conta_da_battletag(battletag), safe="")
    dados = _pegar(api, f"/d3/profile/{conta}/hero/{int(id_heroi)}")
    itens = _pegar(api, f"/d3/profile/{conta}/hero/{int(id_heroi)}/items")
    skills = dados.get("skills") or {}
    return {
        "id": dados.get("id"),
        "nome": dados.get("name"),
        "classe": CLASSE_DO_PERFIL.get(dados.get("class")),
        "nivel": dados.get("level"),
        "paragon": dados.get("paragonLevel"),
        "atualizado": dados.get("lastUpdated"),
        "itens": {lugar: item_do_perfil(item, ESPACO_DO_PERFIL[lugar])
                  for lugar, item in itens.items() if lugar in ESPACO_DO_PERFIL and isinstance(item, dict)},
        "habilidades": {
            "ativas": [{"habilidade": s["skill"]["slug"], "runa": (s.get("rune") or {}).get("type", "")}
                       for s in skills.get("active", []) if s.get("skill")],
            "passivas": [s["skill"]["slug"] for s in skills.get("passive", []) if s.get("skill")],
        },
    }


def comparar(h: dict, build: dict) -> dict:
    """O herói contra a build: cada item equipado avaliado (mesmo avaliador do F8)
    e as habilidades (tem? runa certa?)."""
    itens = [{"lugar": lugar, "espaco": item["slot"], "item": item, "resultado": avaliar(item, build)}
             for lugar, item in h["itens"].items()]

    da_build = build.get("habilidades") or {"ativas": [], "passivas": []}
    runa_do_heroi = {a["habilidade"]: a["runa"] for a in h["habilidades"]["ativas"]}
    ativas = []
    for a in da_build.get("ativas", []):
        slug, runa = a["habilidade"], a.get("runa", "")
        if slug not in runa_do_heroi:
            estado = "falta"
        elif runa and runa_do_heroi[slug] != runa:
            estado = "runa"
        else:
            estado = "ok"
        ativas.append({"habilidade": slug, "runa": runa, "runa_do_heroi": runa_do_heroi.get(slug), "estado": estado})
    passivas = [{"habilidade": p, "estado": "ok" if p in h["habilidades"]["passivas"] else "falta"}
                for p in da_build.get("passivas", [])]
    sobrando = [a["habilidade"] for a in h["habilidades"]["ativas"]
                if a["habilidade"] not in {x["habilidade"] for x in da_build.get("ativas", [])}]
    sobrando += [p for p in h["habilidades"]["passivas"] if p not in da_build.get("passivas", [])]
    return {
        "itens": itens,
        "habilidades": {"ativas": ativas, "passivas": passivas, "fora_da_build": sobrando},
        "classe_igual": h["classe"] == build.get("classe"),
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    api = Blizzard()
    try:
        if len(sys.argv) == 2:
            for h in herois(api, sys.argv[1]):
                print(f"{h['id']:>12}  {h['nome']:<14} {h['classe'] or '?':<13} nível {h['nivel']}"
                      f"  paragon {h['paragon']}{'  (temporada)' if h['temporada'] else ''}")
            return
        build = next((b for b in carregar_builds() if b["id"] == sys.argv[3]), None)
        if build is None:
            sys.exit(f"Não existe build {sys.argv[3]!r} em builds/.")
        r = comparar(heroi(api, sys.argv[1], int(sys.argv[2])), build)
    except ErroBlizzard as e:
        sys.exit(str(e))
    for x in r["itens"]:
        res = x["resultado"]
        marca = "✅" if res["bate"] else "🟡" if res["por_enquanto"] else "❌"
        falta = [a["rotulo"] for a in res["afixos"] if not a["ok"]]
        print(f"{marca} {x['espaco']:<9} {x['item']['nome']:<32} {res['motivo']}"
              + (f" · falta: {', '.join(falta)}" if falta and (res['bate'] or res['por_enquanto']) else ""))
    for a in r["habilidades"]["ativas"]:
        print({"ok": "✓", "runa": "≈", "falta": "✗"}[a["estado"]], a["habilidade"], a["runa"])


if __name__ == "__main__":
    main()
