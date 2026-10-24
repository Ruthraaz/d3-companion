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
from pathlib import Path

PASTA_BUILDS = Path(__file__).resolve().parent.parent / "builds"

# O parser devolve o encaixe da arma ("1-Hand", "2-Hand"); a build usa "Weapon".
ESPACO_DA_BUILD = {"1-Hand": "Weapon", "2-Hand": "Weapon"}
# Todos os espaços que uma build pode definir (nomes do JSON).
ESPACOS = ["Head", "Shoulders", "Neck", "Torso", "Hands", "Wrists", "Waist",
           "Legs", "Feet", "Finger", "Weapon", "Off-Hand"]

SOQUETE = "@soquete"


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

    nome_espaco = ESPACO_DA_BUILD.get(item.get("slot"), item.get("slot"))
    espaco = build.get("espacos", {}).get(nome_espaco, {})
    geral = build.get("todos_os_espacos", {})

    obrigatorios = _conferir(item, geral.get("obrigatorios", []) + espaco.get("obrigatorios", []))
    desejaveis = _conferir(item, geral.get("desejaveis", []) + espaco.get("desejaveis", []))
    total = len(desejaveis["ok"]) + len(desejaveis["faltando"])
    nota = round(len(desejaveis["ok"]) / total, 2) if total else 1.0

    itens = espaco.get("itens", [])
    exige_ancient = espaco.get("exige_ancient", build.get("exige_ancient", False))
    nome = item.get("nome") or ""

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
    }


def carregar_builds(pasta: Path = PASTA_BUILDS) -> list[dict]:
    """Lê builds/*.json. Cada build ganha um "id" = nome do arquivo sem .json
    (ex.: "legacy_of_nightmares"), que não muda se o apelido mudar."""
    builds = []
    for p in sorted(pasta.glob("*.json")):
        build = json.loads(p.read_text(encoding="utf-8"))
        build["id"] = p.stem
        builds.append(build)
    return builds


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
    if len(sys.argv) < 2:
        print("Uso: python src/avaliador.py <imagem.png | texto.txt>")
        sys.exit(1)
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
