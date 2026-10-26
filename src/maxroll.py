"""
Builds do planejador do Maxroll (maxroll.gg/d3/planner/<número>) no formato do app.

O Maxroll não tem API oficial. Lemos o mesmo endereço que a própria página
do guia usa pra mostrar a build (planners.maxroll.gg/profiles/load/d3/<n>),
só quando o Arthur cola um link. Link de guia: lemos a página do guia uma vez
pra achar as builds que ela mostra (as do seguidor ficam de fora). Se o site mudar o formato,
é aqui que quebra — e a mensagem de erro diz isso.

O que vem do Maxroll: itens (pelo código da Blizzard, ex. "Unique_Helm_Set_03_p2"),
gemas, cubo de Kanai, habilidades com runa e passivas. Cada planner pode ter
vários "perfis" (variações da build: push, speed, bounties...).

Os nomes dos itens vêm do arquivo de dados do planejador (data.json, guardado
em dados/maxroll/). Os códigos das habilidades são convertidos pros da Blizzard
("entanglingshot" -> "entangling-shot"), que é de onde vêm ícone e descrição.

Catálogo: a lista de guias vem do mapa do site (maxroll.gg/d3/sitemap.xml),
um arquivo pequeno, lido no máximo uma vez por dia. As builds de cada guia
só são baixadas quando o Arthur abre o guia na janela.

Uso (o link pode ser do guia ou do planejador):
    python src/maxroll.py <link>                                # mostra as builds, os perfis e a build
    python src/maxroll.py <link> --build 1 --perfil 2 --salvar  # grava em builds/ (sem sobrescrever)
"""

import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CACHE = RAIZ / "dados" / "maxroll"
URL_PLANNER = "https://planners.maxroll.gg/profiles/load/d3/{}"
URL_DADOS = "https://assets-ng.maxroll.gg/d3planner/data.json"
URL_MAPA_DO_SITE = "https://maxroll.gg/d3/sitemap.xml"
VERSAO_DO_CACHE = 2  # sobe quando o que guardamos do data.json muda
CABECALHO = {"User-Agent": "D3Companion/1.0 (app pessoal; uma build por vez)"}

# classe do Maxroll -> (classe nas builds, atributo principal, rótulo, chave do atributo no Maxroll)
CLASSES = {
    "barbarian": ("Barbarian", "Strength", "Força", "str"),
    "crusader": ("Crusader", "Strength", "Força", "str"),
    "demonhunter": ("Demon Hunter", "Dexterity", "Destreza", "dex"),
    "monk": ("Monk", "Dexterity", "Destreza", "dex"),
    "necromancer": ("Necromancer", "Intelligence", "Inteligência", "int"),
    "witchdoctor": ("Witch Doctor", "Intelligence", "Inteligência", "int"),
    "wizard": ("Wizard", "Intelligence", "Inteligência", "int"),
}

# Afixo do Maxroll -> rótulo curto do selo. O que não está aqui usa o nome do Maxroll.
ROTULOS = {
    "str": "Força", "dex": "Destreza", "int": "Inteligência", "vit": "Vitalidade",
    "chc": "Crítico", "chd": "Dano crítico", "ias": "Vel. de ataque", "cdr": "Recarga",
    "rcr": "Custo de recurso", "area": "Dano em área", "resall": "Resistência total",
    "life": "Vida %", "armor": "Armadura", "lph": "Vida por acerto", "regen": "Vida por segundo",
    "dmgred": "Redução de dano", "edmg": "Dano a elites", "damage": "Dano %", "ms": "Velocidade",
    "dmgphy": "Dano físico", "dmgfir": "Dano de fogo", "dmgcol": "Dano de frio",
    "dmglit": "Dano elétrico", "dmgpsn": "Dano de veneno", "dmgarc": "Dano arcano",
    "dmghol": "Dano sagrado", "damage_demonhunter": "Dano de habilidade",
}
# Não viram regra: armadura base do item, poder lendário, durabilidade e o
# aumento do Caldesann (vem depois, no cubo). Secundários (ouro, raio, XP) também não.
IGNORADOS = {"basearmor", "custom", "dura"}
IGNORADOS_PREFIXO = ("caldesanns_", "leg_")

# espaço do Maxroll -> espaço nas builds (os dois anéis vão juntos em Finger)
ESPACOS = {
    "head": "Head", "shoulders": "Shoulders", "neck": "Neck", "torso": "Torso",
    "hands": "Hands", "wrists": "Wrists", "waist": "Waist", "legs": "Legs",
    "feet": "Feet", "leftfinger": "Finger", "rightfinger": "Finger",
    "mainhand": "Weapon", "offhand": "Off-Hand",
}
CUBO = {"weapon": "arma", "armor": "armadura", "jewelry": "joia"}
RUNAS = ("a", "b", "c", "d", "e")


class ErroMaxroll(Exception):
    """Erro com mensagem em português, pronta pra mostrar ao Arthur."""


def id_do_link(texto: str) -> int:
    """O número do planner num link (ou o próprio número).
    "https://maxroll.gg/d3/planner/345357607#2" -> 345357607."""
    m = re.search(r"planner/(\d+)", texto) or re.fullmatch(r"\s*(\d{6,})\s*", texto)
    if not m:
        raise ErroMaxroll("Não achei a build no link. Cole o link de um guia de D3 do Maxroll "
                          "(maxroll.gg/d3/guides/...) ou do planejador (maxroll.gg/d3/planner/...).")
    return int(m.group(1))


def link_de_guia(texto: str) -> str | None:
    """O endereço do guia, se o texto for um link de guia de D3 do Maxroll."""
    m = re.search(r"(?:https?://)?(?:www\.)?maxroll\.gg/d3/guides/([a-z0-9-]+)", texto.strip())
    return f"https://maxroll.gg/d3/guides/{m.group(1)}" if m else None


def planners_do_link(texto: str, abrir=urllib.request.urlopen) -> list[int]:
    """Os números das builds que um link traz. Link de planner = uma build;
    link de guia = as builds que a página mostra (lidas do HTML do guia)."""
    guia = link_de_guia(texto)
    if guia is None:
        return [id_do_link(texto)]
    try:
        with abrir(urllib.request.Request(guia, headers=CABECALHO), timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ErroMaxroll("Esse guia não existe no Maxroll. O link está certo?") from e
        raise ErroMaxroll(f"O Maxroll respondeu com erro {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErroMaxroll("Não consegui falar com o Maxroll. Está sem internet?") from e
    numeros = list(dict.fromkeys(int(n) for n in re.findall(r'data-d3planner-id="(\d+)"', html)))
    if not numeros:
        raise ErroMaxroll("Não achei nenhuma build nesse guia (o site pode ter mudado).")
    return numeros


# Fim do endereço do guia -> classe do Maxroll. Os de suporte usam "zbarb", "zmonk"...
CLASSE_DO_GUIA = {
    "barbarian": "barbarian", "zbarb": "barbarian", "crusader": "crusader",
    "demon-hunter": "demonhunter", "monk": "monk", "zmonk": "monk",
    "necromancer": "necromancer", "znecromancer": "necromancer",
    "witch-doctor": "witchdoctor", "wizard": "wizard", "zwiz": "wizard",
}
# Siglas que os guias usam no nome (lod = Legacy of Dreams...).
SIGLAS = {"lod": "LoD", "lon": "LoN", "ue": "UE", "ik": "IK", "aov": "AoV", "sotl": "SotL",
          "dmo": "DMO", "ww": "WW", "hota": "HotA", "god": "GoD", "ha": "HA", "wod": "WoD",
          "of": "of", "the": "the"}


def guia_do_link(link: str) -> dict | None:
    """Endereço de um guia -> {link, titulo, classe}; None se não for guia de classe.
    "…/guides/shadow-impale-demon-hunter-guide" -> titulo "Shadow Impale", classe "Demon Hunter"."""
    m = re.fullmatch(r"https://maxroll\.gg/d3/guides/([a-z0-9-]+)", link.strip())
    if not m:
        return None
    nome = m.group(1).removesuffix("-guide")
    for fim in sorted(CLASSE_DO_GUIA, key=len, reverse=True):  # "witch-doctor" antes de "doctor"
        if nome == fim or nome.endswith("-" + fim):
            palavras = nome.removesuffix(fim).strip("-").split("-")
            titulo = " ".join(SIGLAS.get(p, p.capitalize()) for p in palavras if p)
            return {"link": link.strip(), "titulo": "Suporte" if titulo == "Support" else titulo or "Guia",
                    "classe": CLASSES[CLASSE_DO_GUIA[fim]][0]}
    return None


def catalogo(pasta: Path = PASTA_CACHE, abrir=urllib.request.urlopen, atualizar: bool = False) -> list[dict]:
    """Todos os guias de classe do Maxroll, por classe e nome. Guardado em
    dados/maxroll/ e lido de novo do site no máximo uma vez por dia. Sem
    internet, usa o guardado (se houver)."""
    arquivo = pasta / "catalogo.json"
    hoje = datetime.date.today().isoformat()
    guardado = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else None
    if guardado and guardado.get("dia") == hoje and not atualizar:
        return guardado["guias"]
    try:
        with abrir(urllib.request.Request(URL_MAPA_DO_SITE, headers=CABECALHO), timeout=30) as r:
            mapa = r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if guardado:
            return guardado["guias"]
        raise ErroMaxroll("Não consegui falar com o Maxroll. Está sem internet?") from e
    links = dict.fromkeys(re.findall(r"<loc>(https://maxroll\.gg/d3/guides/[a-z0-9-]+)</loc>", mapa))
    guias = sorted((g for g in map(guia_do_link, links) if g), key=lambda g: (g["classe"], g["titulo"]))
    if not guias:
        if guardado:
            return guardado["guias"]
        raise ErroMaxroll("Não achei a lista de guias no Maxroll (o site pode ter mudado).")
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"dia": hoje, "guias": guias}, ensure_ascii=False), encoding="utf-8")
    return guias


SEGUIDORES = re.compile(r"enchantress|templar|scoundrel|follower", re.I)


def e_de_seguidor(planner: dict) -> bool:
    """Build do seguidor (os guias trazem a da Enchantress junto): não é do herói."""
    return bool(SEGUIDORES.search(planner["_nome"]))


def builds_do_heroi(planners: list[dict], texto: str) -> list[dict]:
    """Só as builds de herói que o app conhece. Num guia, só as da classe do
    guia: o de Witch Doctor traz um "DH Speed" de Demon Hunter de exemplo."""
    herois = [p for p in planners if not e_de_seguidor(p) and classe_do_planner(p)]
    guia = guia_do_link(link_de_guia(texto) or "")
    if guia:
        herois = [p for p in herois if classe_do_planner(p) == guia["classe"]]
    return herois


def _baixar(url: str, abrir=urllib.request.urlopen):
    try:
        with abrir(urllib.request.Request(url, headers=CABECALHO), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ErroMaxroll("O Maxroll não achou essa build. O link está certo e a build é pública?") from e
        raise ErroMaxroll(f"O Maxroll respondeu com erro {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErroMaxroll("Não consegui falar com o Maxroll. Está sem internet?") from e
    except json.JSONDecodeError as e:
        raise ErroMaxroll("O Maxroll respondeu num formato que o app não conhece "
                          "(o site pode ter mudado).") from e


def baixar_planner(numero: int, abrir=urllib.request.urlopen) -> dict:
    """O planner como o Maxroll guarda: nome, classe e os perfis (variações)."""
    bruto = _baixar(URL_PLANNER.format(numero), abrir)
    try:
        dados = json.loads(bruto["data"]) if isinstance(bruto["data"], str) else bruto["data"]
        if "profiles" not in dados and "items" in dados:
            # Planner de um perfil só: o próprio "data" é o perfil.
            dados = {"profiles": [dados], "activeProfile": 0, "class": dados.get("class")}
        dados["profiles"]  # noqa: B018 — só confere que existe
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        raise ErroMaxroll("O Maxroll respondeu num formato que o app não conhece "
                          "(o site pode ter mudado).") from e
    dados["_nome"] = bruto.get("name") or dados.get("name") or f"Maxroll {numero}"
    dados["_numero"] = numero
    return dados


def dados_do_planejador(pasta: Path = PASTA_CACHE, abrir=urllib.request.urlopen) -> dict:
    """Nomes dos itens e das gemas lendárias (data.json do planejador, ~1,3 MB).
    Baixado uma vez e guardado em dados/maxroll/."""
    arquivo = pasta / "data.json"
    if arquivo.exists():
        guardado = json.loads(arquivo.read_text(encoding="utf-8"))
        if guardado.get("versao") == VERSAO_DO_CACHE:  # cache antigo: baixa de novo
            return guardado
    dados = _baixar(URL_DADOS, abrir)
    def por_id(colecao):  # o data.json traz lista de itens; dicionário fica igual
        valores = colecao.values() if isinstance(colecao, dict) else colecao
        return {v["id"]: v for v in valores if isinstance(v, dict) and v.get("id")}
    gemas = dados.get("legendaryGems", {})
    pequeno = {"versao": VERSAO_DO_CACHE,
               "items": {k: {"name": v.get("name"), "ids": v.get("ids", [])}
                         for k, v in por_id(dados.get("items", [])).items()},
               # As gemas ficam pela chave do Maxroll ("zei"), que é como o planner as cita.
               "legendaryGems": {k: {"name": v.get("name")} for k, v in gemas.items()},
               # Texto de cada afixo, igual ao do jogo: "Critical Hit Chance Increased by %.1f%%".
               "stats": {k: {"name": v.get("name"), "format": v.get("format"),
                             "secondary": bool(v.get("secondary")), "args": v.get("args")}
                         for k, v in dados.get("stats", {}).items() if isinstance(v, dict)}}
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(pequeno, ensure_ascii=False), encoding="utf-8")
    return pequeno


def classe_do_planner(planner: dict) -> str | None:
    """A classe como as builds escrevem ("Demon Hunter"), ou None se o app não conhece."""
    classe = planner.get("class") or planner["profiles"][0].get("class")
    return CLASSES[classe][0] if classe in CLASSES else None


def nomes_dos_perfis(planner: dict) -> list[str]:
    return [p.get("name") or f"Perfil {i + 1}" for i, p in enumerate(planner["profiles"])]


def _nome_do_item(codigo: str, dados: dict) -> str | None:
    itens = dados["items"]
    if codigo in itens:
        return itens[codigo]["name"]
    for item in itens.values():  # código antigo/alternativo do mesmo item
        if codigo in item.get("ids", []):
            return item["name"]
    return None


def modelo_do_formato(formato: str) -> str:
    """Texto do Maxroll -> modelo do app (o mesmo que o parser tira da dica):
    "Critical Hit Chance Increased by %.1f%%" -> "Critical Hit Chance Increased by #%"."""
    texto = formato.replace("%%", "\0")
    texto = re.sub(r"%[-+]?\d*(?:\.\d+)?[dfs]", "#", texto)
    return texto.replace("\0", "%")


def regras_do_item(stats: dict, dados: dict, atributo: str, habilidades: dict[str, dict],
                   na_arma: bool = False) -> list[dict]:
    """Os afixos que o guia escolheu pra um item -> regras desejáveis do espaço.

    `atributo` é a chave do atributo principal ("dex"), que já é obrigatório em
    todos os espaços e não se repete aqui. `habilidades`: código sem hífen ->
    habilidade da Blizzard (pra "Increases Impale Damage by #%")."""
    regras = []
    for chave in stats:
        if chave == "sockets":
            regras.append({"modelo": "@soquete", "rotulo": "Encaixe"})
            continue
        if chave.startswith("skill_"):
            # skill_demonhunter_impale -> "Increases Impale Damage by 13% (Demon Hunter Only)"
            h = habilidades.get(chave.split("_", 2)[-1])
            if h and h.get("nome"):
                regras.append({"modelo": f"Increases {h['nome']} Damage by #% *",
                               "rotulo": f"Dano de {h.get('nome_pt') or h['nome']}"})
            continue
        if chave == atributo or chave in IGNORADOS or chave.startswith(IGNORADOS_PREFIXO):
            continue
        info = dados.get("stats", {}).get(chave)
        if not info or info.get("secondary") or not info.get("name"):
            continue
        if info.get("format"):
            modelo = modelo_do_formato(info["format"])
        elif info.get("args") == 2:  # dano com faixa: "+1015-1214 Cold Damage"
            modelo = f"+#-# {info['name']}"
        else:
            modelo = f"+# {info['name']}"
        if chave.startswith("wpn"):
            rotulo = "Dano da arma" if na_arma else "Dano mín–máx"
        else:
            rotulo = ROTULOS.get(chave, info["name"])
        regras.append({"modelo": modelo, "rotulo": rotulo})
    return regras


def _sem_hifen(slug: str) -> str:
    return slug.replace("-", "").replace(" ", "").lower()


def converter(planner: dict, dados: dict, habilidades_da_classe: dict | None = None,
              perfil: int | None = None) -> dict:
    """Um perfil do planner -> build no formato do app (builds/*.json).

    `habilidades_da_classe` é o que blizzard.habilidades() devolve; serve pra
    trocar o código do Maxroll pelo da Blizzard. Sem ele, fica o do Maxroll.
    """
    if perfil is None:
        perfil = planner.get("activeProfile") or 0
    if not 0 <= perfil < len(planner["profiles"]):
        raise ErroMaxroll(f"Essa build tem {len(planner['profiles'])} perfis; "
                          f"escolha de 1 a {len(planner['profiles'])}.")
    p = planner["profiles"][perfil]
    classe_mx = p.get("class") or planner.get("class")
    if classe_mx not in CLASSES:
        raise ErroMaxroll(f"Classe {classe_mx!r} do Maxroll não é conhecida pelo app.")
    classe, atributo, rotulo, chave_do_atributo = CLASSES[classe_mx]

    # código sem hífen ("smokescreen") -> habilidade da Blizzard (slug, nome, nome_pt)
    da_blizzard = {}
    if habilidades_da_classe:
        for tipo in ("ativas", "passivas"):
            da_blizzard.update({_sem_hifen(h["slug"]): h for h in habilidades_da_classe[tipo]})

    espacos, gemas, desconhecidos = {}, [], []
    for espaco_mx, item in (p.get("items") or {}).items():
        if espaco_mx not in ESPACOS or not item or not item.get("id"):
            continue
        nome = _nome_do_item(item["id"], dados)
        if nome is None:
            desconhecidos.append(item["id"])
            continue
        espaco = espacos.setdefault(ESPACOS[espaco_mx], {"itens": []})
        if nome not in espaco["itens"]:
            espaco["itens"].append(nome)
        # Os afixos que o guia escolheu viram desejáveis. Nos anéis (dois itens no
        # mesmo espaço) junta os dos dois, sem repetir.
        desejaveis = espaco.setdefault("desejaveis", [])
        for regra in regras_do_item(item.get("stats") or {}, dados, chave_do_atributo, da_blizzard,
                                    na_arma=ESPACOS[espaco_mx] == "Weapon"):
            if regra["modelo"] not in {r["modelo"] for r in desejaveis}:
                desejaveis.append(regra)
        for gema in item.get("gems") or []:
            # Gema lendária vem como ["zei", 150]; a comum como [9, "topaz"].
            if gema and isinstance(gema[0], str) and gema[0] in dados["legendaryGems"]:
                nome_gema = dados["legendaryGems"][gema[0]]["name"]
                if nome_gema not in gemas:
                    gemas.append(nome_gema)

    cubo = {}
    for parte_mx, parte in CUBO.items():
        codigo = (p.get("kanai") or {}).get(parte_mx)
        if codigo:
            nome = _nome_do_item(codigo, dados)
            if nome:
                cubo[parte] = nome
            else:
                desconhecidos.append(codigo)

    por_codigo = {codigo: h["slug"] for codigo, h in da_blizzard.items()}
    # Runa "x" no Maxroll = habilidade sem runa; vira "" (a build só aceita a-e).
    ativas = [{"habilidade": por_codigo.get(_sem_hifen(s[0]), s[0]),
               "runa": s[1] if len(s) > 1 and s[1] in RUNAS else ""}
              for s in (p.get("skills") or []) if s and s[0]]
    passivas = [por_codigo.get(_sem_hifen(s), s) for s in (p.get("passives") or []) if s]

    nome_do_perfil = nomes_dos_perfis(planner)[perfil]
    build = {
        "formato": 1,
        "nome": f"{planner['_nome']} — {nome_do_perfil}" if len(planner["profiles"]) > 1 else planner["_nome"],
        "apelido": planner["_nome"],
        "classe": classe,
        "exige_ancient": False,
        "fonte": {"site": "maxroll", "planner": planner["_numero"], "perfil": nome_do_perfil,
                  "link": f"https://maxroll.gg/d3/planner/{planner['_numero']}"}
                 | ({"guia": planner["_guia"]} if planner.get("_guia") else {}),
        "todos_os_espacos": {"obrigatorios": [{"modelo": f"+# {atributo}", "rotulo": rotulo}]},
        "espacos": espacos,
        "gemas": gemas,
        "cubo": cubo,
        "habilidades": {"ativas": ativas, "passivas": passivas},
    }
    paragon = p.get("paragon") or {}
    pontos = paragon.get("data")
    if (isinstance(pontos, list) and len(pontos) == 4
            and all(isinstance(g, list) and len(g) == 4 and all(isinstance(n, int) for n in g) for g in pontos)):
        # Mesma ordem do jogo: Principal (atributo, Vitalidade, Velocidade, Recurso máx.),
        # Ataque, Defesa e Utilidade.
        build["paragon"] = {"nivel": int(paragon.get("level") or 0), "pontos": pontos}
    if desconhecidos:
        build["_itens_nao_reconhecidos"] = desconhecidos
    return build


def nome_do_arquivo(build: dict) -> str:
    """"Sanc UE Multishot" -> "sanc_ue_multishot"."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", build["apelido"]).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_") or "build_maxroll"


def salvar_build(build: dict, pasta: Path = RAIZ / "builds") -> Path:
    """Grava a build em builds/<apelido>.json. Nunca sobrescreve: se o nome já
    existe, usa _2, _3... Devolve o arquivo criado."""
    base = nome_do_arquivo(build)
    destino, n = pasta / f"{base}.json", 2
    while destino.exists():
        destino, n = pasta / f"{base}_{n}.json", n + 1
    destino.write_text(json.dumps(build, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino


def montar(planner: dict, perfil: int | None = None, apelido: str | None = None,
           blizzard=None) -> dict:
    """Planner já baixado -> build pronta pra salvar, com os códigos das
    habilidades da Blizzard. Sem Blizzard (chave/internet), ficam os do Maxroll."""
    from blizzard import Blizzard, ErroBlizzard
    classe = classe_do_planner(planner)
    if classe is None:
        raise ErroMaxroll("Essa build é de uma classe que o app não conhece.")
    try:
        habilidades = (blizzard or Blizzard()).habilidades(classe)
    except ErroBlizzard:
        habilidades = None
    build = converter(planner, dados_do_planejador(), habilidades, perfil)
    if apelido and apelido.strip():
        build["apelido"] = apelido.strip()
    return build


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    def opcao(nome):
        if nome in sys.argv:
            return int(sys.argv[sys.argv.index(nome) + 1]) - 1
        return None
    numeros_das_opcoes = {sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a in ("--perfil", "--build")}
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in numeros_das_opcoes]
    if not args:
        print(__doc__)
        sys.exit(1)
    try:
        planners = [baixar_planner(n) for n in planners_do_link(args[0])]
        herois = [p for p in planners if not e_de_seguidor(p)] or planners
        print("Builds no link:")
        for i, p in enumerate(herois, 1):
            print(f"  {i}. {p['_nome']} ({classe_do_planner(p) or p.get('class')}) — {len(p['profiles'])} perfis")
        escolhido = herois[opcao("--build") or 0]
        build = montar(escolhido, opcao("--perfil"))
    except (ErroMaxroll, IndexError) as e:
        print(f"❌ {e if isinstance(e, ErroMaxroll) else 'Esse número de build não existe no link.'}")
        sys.exit(1)

    print(f"\n{escolhido['_nome']} — perfis:")
    for i, nome in enumerate(nomes_dos_perfis(escolhido), 1):
        print(f"  {'→' if nome == build['fonte']['perfil'] else ' '} {i}. {nome}")
    print(json.dumps(build, ensure_ascii=False, indent=2))
    if "--salvar" in sys.argv:
        print(f"✅ Salvo em builds/{salvar_build(build).name}")


if __name__ == "__main__":
    main()
