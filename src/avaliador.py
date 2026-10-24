"""
Etapa 3 — Avaliador: compara um item (saída do parser) com as builds.

Uso:
    python src/avaliador.py samples/set_antique_vintage_boots.png
    python src/avaliador.py tests/ocr/set_antique_vintage_boots.txt

As builds ficam em builds/*.json, num formato próprio do app (veja o README).
Se um dia entrarem builds de sites (Maxroll, Icy Veins), elas serão só
TRADUZIDAS pra esse formato; o avaliador continua conhecendo só ele.

Regras:
  - "bate" = item permitido no espaço (lista "itens" vazia = qualquer um)
             + todos os afixos obrigatórios + Ancient, se a build exigir
             + não é de outra classe.
  - "nota" = fração dos afixos desejáveis que o item tem (0 a 1).
"""

import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path

PASTA_BUILDS = Path(__file__).resolve().parent.parent / "builds"

# O parser devolve o encaixe da arma ("1-Hand", "2-Hand"); a build usa "Weapon".
ESPACO_DA_BUILD = {"1-Hand": "Weapon", "2-Hand": "Weapon"}
# Todos os espaços que uma build pode definir (nomes do JSON).
ESPACOS = ["Head", "Shoulders", "Neck", "Torso", "Hands", "Wrists", "Waist",
           "Legs", "Feet", "Finger", "Weapon", "Off-Hand"]

SOQUETE = "@soquete"

PARTES_DO_CUBO = ("arma", "armadura", "joia")


# ---------------------------------------------------------------- afixos

def _normalizar(texto: str) -> str:
    """Comparação tolerante: ignora maiúsculas, espaços extras e ponto final."""
    return " ".join(texto.lower().split()).rstrip(".")


def _padrao(modelo: str) -> re.Pattern:
    """Modelo da build -> regex. "*" vale por uma ou mais palavras:
    "+# * Resistance" aceita "+# Cold Resistance" e "+# Fire Resistance"."""
    partes = [r"\S+(?: \S+)*?" if p == "*" else re.escape(p)
              for p in re.split(r"(\*)", _normalizar(modelo))]
    return re.compile("".join(partes) + r"$")


def _tem_afixo(item: dict, regra: str | dict) -> bool:
    """A regra é um modelo ("+# Dexterity"), "@soquete", ou um objeto
    {"modelo": ..., "rotulo": "Destreza", "minimo": N} (rotulo e minimo opcionais)."""
    modelo = regra["modelo"] if isinstance(regra, dict) else regra
    minimo = regra.get("minimo") if isinstance(regra, dict) else None

    if modelo == SOQUETE:
        return item.get("soquetes", 0) > 0

    padrao = _padrao(modelo)
    for afixo in item.get("primarios", []) + item.get("secundarios", []):
        if padrao.match(_normalizar(afixo["modelo"])):
            # Com "minimo", compara o primeiro número do afixo.
            if minimo is None or (afixo["valores"] and afixo["valores"][0] >= minimo):
                return True
    return False


def _rotulo(regra: str | dict) -> str:
    """Nome curto pra mostrar (ex.: "Destreza"); sem rótulo, o próprio modelo."""
    if isinstance(regra, str):
        return regra
    texto = regra.get("rotulo") or regra["modelo"]
    if regra.get("minimo") is not None:
        texto += f' (mín. {regra["minimo"]})'
    return texto


def _conferir(item: dict, regras: list) -> dict:
    lista = [{"rotulo": _rotulo(r), "ok": _tem_afixo(item, r)} for r in regras]
    return {
        "ok": [a["rotulo"] for a in lista if a["ok"]],
        "faltando": [a["rotulo"] for a in lista if not a["ok"]],
        "lista": lista,  # na ordem da build, pro selo do overlay
    }


# ---------------------------------------------------------------- avaliação

def avaliar(item: dict, build: dict) -> dict:
    """Avalia um item contra UMA build."""
    resultado = {"build": build["nome"], "apelido": build.get("apelido", build["nome"])}

    if item.get("tipo") == "Gem":
        bate = item.get("nome") in build.get("gemas", [])
        vazio = {"ok": [], "faltando": [], "lista": []}
        return resultado | {
            "bate": bate,
            "motivo": "Gema da build" if bate else "Gema fora da build",
            "obrigatorios": vazio,
            "desejaveis": vazio,
            "afixos": [],
            "nota": 1.0 if bate else 0.0,
        }

    nome = item.get("nome") or ""
    cubo = {n.lower(): parte for parte, n in build.get("cubo", {}).items()}
    if nome.lower() in cubo and not (item.get("classe") and item["classe"] != build.get("classe")):
        # Item do cubo: o que vale é o poder lendário (extraído no cubo de Kanai),
        # então afixos e Ancient não importam.
        vazio = {"ok": [], "faltando": [], "lista": []}
        return resultado | {
            "bate": True,
            "motivo": f"Vai no cubo de Kanai ({cubo[nome.lower()]})",
            "obrigatorios": vazio,
            "desejaveis": vazio,
            "afixos": [],
            "nota": 1.0,
        }

    nome_espaco = ESPACO_DA_BUILD.get(item.get("slot"), item.get("slot"))
    espaco = build.get("espacos", {}).get(nome_espaco, {})
    geral = build.get("todos_os_espacos", {})

    obrigatorios = _conferir(item, geral.get("obrigatorios", []) + espaco.get("obrigatorios", []))
    desejaveis = _conferir(item, geral.get("desejaveis", []) + espaco.get("desejaveis", []))
    total = len(desejaveis["ok"]) + len(desejaveis["faltando"])
    nota = round(len(desejaveis["ok"]) / total, 2) if total else 1.0

    itens = espaco.get("itens", [])
    exige_ancient = espaco.get("exige_ancient", build.get("exige_ancient", False))

    # A primeira regra que falhar explica o "não serve".
    if item.get("classe") and item["classe"] != build.get("classe"):
        bate, motivo = False, f"Item de {item['classe']}"
    elif itens and nome.lower() not in {i.lower() for i in itens}:
        bate, motivo = False, "A build pede: " + " ou ".join(itens)
    elif exige_ancient and "Ancient" not in item.get("qualidade", ""):
        bate, motivo = False, "Precisa ser Ancient"
    elif obrigatorios["faltando"]:
        bate, motivo = False, "Falta: " + ", ".join(obrigatorios["faltando"])
    else:
        bate = True
        motivo = f"Item da build: {nome}" if itens else "Afixos obrigatórios ok"

    return resultado | {
        "bate": bate,
        "motivo": motivo,
        "obrigatorios": obrigatorios,
        "desejaveis": desejaveis,
        "afixos": obrigatorios["lista"] + desejaveis["lista"],
        "nota": nota,
    }


def ficha_da_build(build: dict) -> dict:
    """A build do jeito que a janela mostra: por espaço, os itens e os rótulos
    já somados com as regras de "todos_os_espacos" (as mesmas que o avaliador usa)."""
    geral = build.get("todos_os_espacos", {})
    definidos = build.get("espacos", {})
    espacos = {}
    # Espaço que a build não define NÃO é "não serve": o avaliador ainda aplica
    # as regras de todos_os_espacos nele. "definido" diferencia os dois na tela.
    for nome in ESPACOS + [n for n in definidos if n not in ESPACOS]:
        espaco = definidos.get(nome, {})
        espacos[nome] = {
            "definido": nome in definidos,
            "itens": espaco.get("itens", []),
            "obrigatorios": [_rotulo(r) for r in geral.get("obrigatorios", []) + espaco.get("obrigatorios", [])],
            "desejaveis": [_rotulo(r) for r in geral.get("desejaveis", []) + espaco.get("desejaveis", [])],
            "exige_ancient": espaco.get("exige_ancient", build.get("exige_ancient", False)),
        }
    return {
        "id": build.get("id"),
        "nome": build["nome"],
        "apelido": build.get("apelido", build["nome"]),
        "classe": build.get("classe"),
        "exige_ancient": build.get("exige_ancient", False),
        "gerais": {
            "obrigatorios": [_rotulo(r) for r in geral.get("obrigatorios", [])],
            "desejaveis": [_rotulo(r) for r in geral.get("desejaveis", [])],
        },
        "espacos": espacos,
        "gemas": build.get("gemas", []),
        "cubo": build.get("cubo", {}),
        "habilidades": build.get("habilidades", {"ativas": [], "passivas": []}),
        "fonte": build.get("fonte"),
    }


# ---------------------------------------------------------------- conferir builds
# Pra uma classe nova entrar "só escrevendo JSON", o JSON errado tem que avisar.
# Sem isso, "Hand" no lugar de "Hands" ou "desejavel" no lugar de "desejaveis"
# fazia a regra sumir calada; e uma vírgula faltando derrubava o app inteiro.

CHAVES_DA_BUILD = {"formato", "nome", "apelido", "classe", "exige_ancient",
                   "todos_os_espacos", "espacos", "gemas", "cubo", "habilidades", "fonte"}
CHAVES_DAS_HABILIDADES = {"ativas", "passivas"}
CHAVES_DA_ATIVA = {"habilidade", "runa"}
RUNAS = {"", "a", "b", "c", "d", "e"}  # a letra que a Blizzard e o Maxroll usam pra cada runa
CHAVES_DO_ESPACO = {"itens", "obrigatorios", "desejaveis", "exige_ancient"}
CHAVES_GERAIS = {"obrigatorios", "desejaveis"}
CHAVES_DA_REGRA = {"modelo", "rotulo", "minimo"}


def _sugestao(palavra: str, opcoes) -> str:
    perto = get_close_matches(palavra, list(opcoes), n=1, cutoff=0.6)
    return f" Quis dizer {perto[0]!r}?" if perto else ""


def _chaves_desconhecidas(onde: str, objeto: dict, validas: set) -> list[str]:
    # Chave começando com "_" é comentário (JSON não tem comentário de verdade).
    return [f"{onde}: chave {k!r} não existe.{_sugestao(k, validas)}"
            for k in objeto if k not in validas and not k.startswith("_")]


def _problemas_das_regras(onde: str, regras) -> list[str]:
    if not isinstance(regras, list):
        return [f"{onde}: precisa ser uma lista [ ... ]."]
    problemas = []
    for n, regra in enumerate(regras, 1):
        lugar = f"{onde}, regra {n}"
        if isinstance(regra, str):
            continue
        if not isinstance(regra, dict) or not isinstance(regra.get("modelo"), str):
            problemas.append(f'{lugar}: use "+# Dexterity" ou {{"modelo": "+# Dexterity", "rotulo": "Destreza"}}.')
            continue
        problemas += _chaves_desconhecidas(lugar, regra, CHAVES_DA_REGRA)
        minimo = regra.get("minimo")
        if minimo is not None and (isinstance(minimo, bool) or not isinstance(minimo, (int, float))):
            problemas.append(f"{lugar}: \"minimo\" precisa ser um número, sem aspas.")
    return problemas


def _lista_de_textos(onde: str, valor) -> list[str]:
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        return [f'{onde}: precisa ser uma lista de nomes, ex.: ["Nome do item"].']
    return []


def problemas_da_build(build) -> list[str]:
    """Tudo que está errado na build, em português. Lista vazia = build ok."""
    from parser import CLASSES  # aqui: o avaliador não precisa do parser pro resto

    if not isinstance(build, dict):
        return ["O arquivo precisa ser um objeto JSON { ... }."]
    problemas = []
    if build.get("formato") != 1:
        problemas.append('"formato" precisa ser 1.')
    if not isinstance(build.get("nome"), str) or not build["nome"].strip():
        problemas.append('Falta o "nome" da build.')
    if build.get("classe") not in CLASSES:
        problemas.append(f"Classe {build.get('classe')!r} não existe."
                         f"{_sugestao(str(build.get('classe')), CLASSES)} Opções: {', '.join(CLASSES)}.")
    problemas += _chaves_desconhecidas("build", build, CHAVES_DA_BUILD)

    gerais = build.get("todos_os_espacos", {})
    if not isinstance(gerais, dict):
        problemas.append('"todos_os_espacos" precisa ser um objeto { ... }.')
    else:
        problemas += _chaves_desconhecidas("todos_os_espacos", gerais, CHAVES_GERAIS)
        for chave in CHAVES_GERAIS & set(gerais):
            problemas += _problemas_das_regras(f"todos_os_espacos.{chave}", gerais[chave])

    espacos = build.get("espacos", {})
    if not isinstance(espacos, dict):
        problemas.append('"espacos" precisa ser um objeto { ... }.')
        espacos = {}
    for nome, espaco in espacos.items():
        if nome not in ESPACOS:
            problemas.append(f"Espaço {nome!r} não existe.{_sugestao(nome, ESPACOS)} "
                             f"Opções: {', '.join(ESPACOS)}.")
            continue
        if not isinstance(espaco, dict):
            problemas.append(f"{nome}: precisa ser um objeto {{ ... }}.")
            continue
        problemas += _chaves_desconhecidas(nome, espaco, CHAVES_DO_ESPACO)
        if "itens" in espaco:
            problemas += _lista_de_textos(f"{nome}.itens", espaco["itens"])
        for chave in ("obrigatorios", "desejaveis"):
            if chave in espaco:
                problemas += _problemas_das_regras(f"{nome}.{chave}", espaco[chave])

    if "gemas" in build:
        problemas += _lista_de_textos("gemas", build["gemas"])
    problemas += _problemas_do_cubo(build.get("cubo", {}))
    problemas += _problemas_das_habilidades(build.get("habilidades", {}))
    if not isinstance(build.get("fonte", {}), dict):
        problemas.append('"fonte" precisa ser um objeto { ... }.')
    return problemas


def _problemas_do_cubo(cubo) -> list[str]:
    if not isinstance(cubo, dict):
        return ['"cubo" precisa ser um objeto, ex.: { "arma": "...", "armadura": "...", "joia": "..." }.']
    problemas = _chaves_desconhecidas("cubo", cubo, set(PARTES_DO_CUBO))
    for parte in set(PARTES_DO_CUBO) & set(cubo):
        if not isinstance(cubo[parte], str) or not cubo[parte].strip():
            problemas.append(f"cubo.{parte}: precisa ser o nome do item.")
    return problemas


def _problemas_das_habilidades(hab) -> list[str]:
    if not isinstance(hab, dict):
        return ['"habilidades" precisa ser um objeto { "ativas": [...], "passivas": [...] }.']
    problemas = _chaves_desconhecidas("habilidades", hab, CHAVES_DAS_HABILIDADES)
    ativas = hab.get("ativas", [])
    if not isinstance(ativas, list) or len(ativas) > 6:
        problemas.append("habilidades.ativas: precisa ser uma lista com até 6 habilidades.")
    else:
        for i, ativa in enumerate(ativas, 1):
            onde = f"habilidades.ativas[{i}]"
            if not isinstance(ativa, dict) or not isinstance(ativa.get("habilidade"), str):
                problemas.append(f'{onde}: precisa ser {{ "habilidade": "multishot", "runa": "a" }}.')
                continue
            problemas += _chaves_desconhecidas(onde, ativa, CHAVES_DA_ATIVA)
            if ativa.get("runa", "") not in RUNAS:
                problemas.append(f"{onde}: runa {ativa['runa']!r} não existe. Use uma letra de a até e.")
    passivas = hab.get("passivas", [])
    if not isinstance(passivas, list) or len(passivas) > 4:
        problemas.append("habilidades.passivas: precisa ser uma lista com até 4 passivas.")
    else:
        problemas += _lista_de_textos("habilidades.passivas", passivas)
    return problemas


def ler_builds(pasta: Path = PASTA_BUILDS) -> tuple[list[dict], dict[str, list[str]]]:
    """(builds que estão ok, {arquivo: problemas}). Build com problema fica de fora;
    as outras continuam funcionando."""
    builds, problemas = [], {}
    for p in sorted(pasta.glob("*.json")):
        try:
            build = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            problemas[p.name] = [f"JSON inválido na linha {erro.lineno}, coluna {erro.colno} "
                                 "(vírgula, aspas ou chave { } faltando ou sobrando?)."]
            continue
        except UnicodeDecodeError:
            problemas[p.name] = ["O arquivo precisa estar salvo em UTF-8."]
            continue
        erros = problemas_da_build(build)
        if erros:
            problemas[p.name] = erros
            continue
        build["id"] = p.stem
        builds.append(build)
    return builds, problemas


def carregar_builds(pasta: Path = PASTA_BUILDS) -> list[dict]:
    """Lê builds/*.json (só as que estão ok). Cada build ganha um "id" = nome do
    arquivo sem .json (ex.: "legacy_of_nightmares"), que não muda se o apelido mudar."""
    return ler_builds(pasta)[0]


def texto_dos_problemas(problemas: dict[str, list[str]]) -> str:
    """Pro terminal: cada arquivo com problema e o que corrigir."""
    linhas = []
    for arquivo, erros in problemas.items():
        linhas.append(f"⚠ builds/{arquivo} ficou de fora:")
        linhas += [f"   - {e}" for e in erros]
    return "\n".join(linhas)


def builds_escolhidas(builds: list[dict], escolha: str) -> list[dict]:
    """A build que a pessoa escolheu na janela (pelo id). Vazio = todas.
    Se o id não existir mais (arquivo renomeado/apagado), volta pra todas."""
    return [b for b in builds if b["id"] == escolha] or builds


def avaliar_todas(item: dict, builds: list[dict]) -> list[dict]:
    """Avalia contra todas as builds; as que batem (e com nota maior) vêm primeiro."""
    resultados = [avaliar(item, b) for b in builds]
    return sorted(resultados, key=lambda r: (not r["bate"], -r["nota"]))


def resumo(item: dict, resultados: list[dict]) -> str:
    """Texto curto com o veredito de cada build (terminal; depois, o overlay)."""
    linhas = [f"{item.get('nome') or '(sem nome)'} — {item.get('qualidade')} {item.get('tipo')}"]
    for r in resultados:
        selo = "✅" if r["bate"] else "❌"
        linhas.append(f"{selo} {r['build']}: {r['motivo']} (nota {r['nota']:.2f})")
        if r["bate"] and r["desejaveis"]["ok"]:
            linhas.append("     tem: " + ", ".join(r["desejaveis"]["ok"]))
    return "\n".join(linhas)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("Uso: python src/avaliador.py <imagem.png | texto.txt>\n"
              "     python src/avaliador.py --conferir [pasta]   (confere as builds)")
        sys.exit(1)
    if sys.argv[1] == "--conferir":
        pasta = Path(sys.argv[2]) if len(sys.argv) > 2 else PASTA_BUILDS
        ok, problemas = ler_builds(pasta)
        for b in ok:
            print(f"✅ {b['id']}.json — {b['nome']} ({b['classe']})")
        if problemas:
            print(texto_dos_problemas(problemas))
        sys.exit(1 if problemas else 0)
    from parser import interpretar

    arquivo = Path(sys.argv[1])
    if arquivo.suffix == ".txt":
        texto = arquivo.read_text(encoding="utf-8")
    else:
        from PIL import Image
        from captura import texto_da_dica  # recorta a dica antes do OCR
        texto = texto_da_dica(Image.open(arquivo))
    item = interpretar(texto)

    sys.stdout.reconfigure(encoding="utf-8")
    print(resumo(item, avaliar_todas(item, carregar_builds())))
