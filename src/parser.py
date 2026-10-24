"""
Etapa 2 — Parser: texto cru do OCR -> item estruturado (dict / JSON).

Uso:
    python src/parser.py samples/lendario_cloak_garwulf.png   (roda o OCR antes)
    python src/parser.py tests/ocr/lendario_cloak_garwulf.txt (usa um texto já lido)

A seção "Stat Changes if Equipped" é ignorada de propósito: o app compara o
item com a BUILD, não com o item equipado. De quebra, é ali que o OCR mais
perde o sinal de menos.

Cada afixo vira {"texto", "modelo", "valores"}:
    "+458 Dexterity" -> modelo "+# Dexterity", valores [458]
O "modelo" é o que o avaliador (Etapa 3) vai comparar com a build.
"""

import json
import re
import sys
from pathlib import Path

QUALIDADE = r"(?:Primal )?(?:Ancient )?(?:Legendary|Set)|Rare|Magic"
SLOTS = {"Head", "Shoulders", "Torso", "Wrists", "Hands", "Waist", "Legs", "Feet",
         "Neck", "Finger", "1-Hand", "2-Hand", "Off-Hand"}
CLASSES = ["Barbarian", "Crusader", "Demon Hunter", "Monk", "Necromancer",
           "Witch Doctor", "Wizard"]

# Palavras que o OCR erra nos atributos (visto nos prints de teste).
CORRECOES = {"Lite": "Life"}

# Palavras que ficam minúsculas no meio do nome ("The Cloak of the Garwulf").
MINUSCULAS = {"of", "the", "and", "a", "an", "to", "in", "on"}

# Linhas que encerram a parte de atributos da dica.
FIM_DOS_ATRIBUTOS = ("Stat Changes", "Required Level", "Account Bound",
                     "Sell Value", "Durability", "Unique Equipped")

NUMERO = r"\d[\d,]*(?:\.\d+)?"
# Caracteres que aparecem em texto de verdade. Qualquer outro (©, ”, |, =, /)
# é sinal de lixo: marcador de afixo lido errado ou pedaço do cenário.
VALIDOS = re.compile(r"^[A-Za-z0-9+\-%'’.,():!?]+$")


# ---------------------------------------------------------------- limpeza

def _lixo_no_inicio(token: str) -> bool:
    return not any(c.isalnum() for c in token) or not VALIDOS.match(token)


def _lixo_no_fim(tokens: list[str]) -> bool:
    t = tokens[-1]
    if not any(c.isalnum() for c in t) or not VALIDOS.match(t):
        return True                      # "?", "i=", "y/", "»,"
    if len(t) == 1 and not t.isdigit() and t not in "aA":
        return True                      # "E", "i"
    if len(t) == 2 and t[0].islower() and t[1].isupper():
        return True                      # "iA"
    if len(tokens) >= 2 and tokens[-2][-1] in ".)" and len(t) <= 4 and not t[0].isdigit():
        return True                      # "Hit. sai,"
    return False


def limpar_linha(linha: str) -> str:
    """Tira o lixo que o OCR deixa nas bordas de uma linha.

    Ex.: "ies +741 Vitality i="                         -> "+741 Vitality"
         "“| @ Chance to Deal 23% Area Damage on Hit. sai," -> "Chance to ... on Hit."
    """
    linha = linha.strip()
    # O "+" de "+458 Dexterity" marca o começo do afixo: o que vem antes é lixo.
    m = re.search(r"\+\d", linha)
    if m and m.start() <= 6:
        linha = linha[m.start():]
    tokens = linha.split()
    while tokens and _lixo_no_inicio(tokens[0]):
        tokens.pop(0)
    while tokens and _lixo_no_fim(tokens):
        tokens.pop()
    return " ".join(tokens)


def _eh_lixo(linha: str) -> bool:
    """Linha que sobrou só com ruído, tipo "rap" ou "ines"."""
    return len(linha.split()) < 2 or sum(c.isalnum() for c in linha) < 5


def agrupar_afixos(linhas: list[str]) -> list[str]:
    """Limpa as linhas e junta afixos que a dica quebrou em duas linhas.

    Junta quando:
      - a linha anterior tem "(" sem fechar   ("...(Demon Hunter" + "Only)")
      - a linha começa com minúscula           ("...bleed for" + "weapon damage...")
      - a anterior é longa e não terminou com "." ou ")" (quebra por largura)
    """
    afixos: list[str] = []
    for bruta in linhas:
        linha = limpar_linha(bruta)
        if not linha:
            continue
        anterior = afixos[-1] if afixos else ""
        if anterior and anterior.count("(") > anterior.count(")"):
            afixos[-1] += " " + linha
        elif _eh_lixo(linha):
            continue
        elif anterior and linha[0].islower():
            # Frase não continua em minúscula depois de ponto: o "." é do OCR.
            afixos[-1] = anterior.removesuffix(".") + " " + linha
        elif anterior and len(anterior) >= 40 and anterior[-1] not in ".)":
            afixos[-1] += " " + linha
        else:
            afixos.append(linha)
    return afixos


# ---------------------------------------------------------------- valores

def _numero(texto: str) -> int | float:
    texto = texto.replace(",", "")
    return float(texto) if "." in texto else int(texto)


def estruturar_afixo(texto: str) -> dict:
    for errado, certo in CORRECOES.items():
        texto = re.sub(rf"\b{errado}\b", certo, texto)
    return {
        "texto": texto,
        "modelo": re.sub(NUMERO, "#", texto),
        "valores": [_numero(n) for n in re.findall(NUMERO, texto)],
    }


def _nome(linha: str) -> str | None:
    """Pega o nome em MAIÚSCULAS e corrige a fonte do título ("@" -> "O")."""
    trechos = [t.strip() for t in re.findall(r"[A-Z@][A-Z@'’ ]*[A-Z@]", linha)]
    trechos = [t for t in trechos if sum(c.isalpha() or c == "@" for c in t) >= 4]
    if not trechos:
        return None
    palavras = max(trechos, key=len).replace("@", "O").lower().split()
    return " ".join(p if i and p in MINUSCULAS else p.capitalize()
                    for i, p in enumerate(palavras))


def _indice(linhas: list[str], padrao: str, inicio: int = 0) -> int | None:
    for i in range(inicio, len(linhas)):
        if re.search(padrao, linhas[i]):
            return i
    return None


def _valor_acima(linhas: list[str], i: int | None, padrao: str) -> str | None:
    """Procura um número nas até 3 linhas acima do rótulo (ex.: "670" acima de "Armor")."""
    if i is None:
        return None
    for j in range(i - 1, max(i - 4, -1), -1):
        m = re.search(padrao, linhas[j])
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------- parser

def interpretar(texto: str) -> dict:
    """Transforma o texto cru do OCR num item (dict pronto pra virar JSON)."""
    linhas = [l for l in texto.splitlines() if l.strip()]

    i_qual = _indice(linhas, rf"\b(?:{QUALIDADE})\s+[A-Z][a-z]+")
    if i_qual is None:
        raise ValueError("Não achei a linha de qualidade (ex.: 'Legendary Cloak').")
    m = re.search(rf"\b({QUALIDADE})\s+(.*)$", linhas[i_qual])
    qualidade, resto = m.group(1), m.group(2).split()

    # Tipo = palavras com inicial maiúscula até o encaixe (Torso, 2-Hand) ou "Rank".
    tipo = []
    for palavra in resto:
        if palavra in SLOTS or palavra == "Rank" or not re.fullmatch(r"[A-Z][a-z]+", palavra):
            break
        tipo.append(palavra)
    slot = next((p for p in resto if p in SLOTS), None)

    nome = None
    for j in range(i_qual - 1, max(i_qual - 5, -1), -1):
        nome = _nome(linhas[j])
        if nome:
            break

    texto_todo = "\n".join(linhas)
    m_nivel = re.search(r"Required Level:?\s*(\d+)", texto_todo)
    item = {
        "nome": nome,
        "qualidade": qualidade,
        "tipo": " ".join(tipo) or None,
    }

    if item["tipo"] == "Gem":
        return item | _gema(linhas, i_qual)

    i_fim = _indice(linhas, "|".join(FIM_DOS_ATRIBUTOS), i_qual) or len(linhas)
    # Títulos de seção, aceitando um pouco de lixo em volta ("°S\ Secondary").
    i_prim = _indice(linhas[:i_fim], r"^.{0,6}\bPrimary\b.{0,6}$", i_qual)
    i_sec = _indice(linhas[:i_fim], r"^.{0,6}\bSecondary\b.{0,6}$", i_qual)
    fim_cabecalho = i_prim or i_sec or i_fim
    cabecalho = linhas[i_qual:fim_cabecalho]

    # O número grande (DPS ou armadura) fica numa linha acima do rótulo.
    # DPS sempre tem uma casa decimal ("2,174.2"); isso evita pegar números da
    # tela de personagem que o OCR mistura no meio (ex.: "244,377").
    dps = _valor_acima(cabecalho, _indice(cabecalho, r"Damage Per Second"),
                       r"\b(\d{1,3}(?:,\d{3})*\.\d)\b")
    armadura = _valor_acima(cabecalho, _indice(cabecalho, r"\bArmor\b"),
                            r"^\W*(\d{1,3}(?:,\d{3})*)\b")
    # Dano da arma: "1794-2159 Damage", sem "+" na frente (com "+" é afixo).
    m_dano = re.search(r"^[^\w+]*(\d+)\s*-\s*(\d+)\s+Damage\b", "\n".join(cabecalho), re.M)
    m_aps = re.search(r"(\d+\.\d+)\s+Attacks per Second", "\n".join(cabecalho))

    def secao(inicio, fim):
        if inicio is None:
            return []
        linhas_secao = [l for l in linhas[inicio + 1:fim] if "Empty Socket" not in l]
        return [estruturar_afixo(a) for a in agrupar_afixos(linhas_secao)]

    return item | {
        "slot": slot,
        "classe": next((c for c in CLASSES for l in cabecalho if c in l), None),
        "armadura": _numero(armadura) if armadura else None,
        "dps": _numero(dps) if dps else None,
        "dano": [int(m_dano.group(1)), int(m_dano.group(2))] if m_dano else None,
        "ataques_por_segundo": float(m_aps.group(1)) if m_aps else None,
        "primarios": secao(i_prim, i_sec if i_sec is not None else i_fim),
        "secundarios": secao(i_sec, i_fim),
        "soquetes": sum("Empty Socket" in l for l in linhas[:i_fim]),
        "nivel_requerido": int(m_nivel.group(1)) if m_nivel else None,
    }


def _gema(linhas: list[str], i_qual: int) -> dict:
    """Gema lendária: efeitos entre "Can be inserted..." e "(Requires Rank 25)"."""
    m_rank = re.search(r"\bRank\s+(\d+)", linhas[i_qual])
    inicio = _indice(linhas, r"inserted into", i_qual)
    inicio = (inicio if inicio is not None else i_qual) + 1
    fim = _indice(linhas, r"\(Requires Rank \d+\)", inicio)
    fim = fim + 1 if fim is not None else (_indice(linhas, "|".join(FIM_DOS_ATRIBUTOS), inicio) or len(linhas))

    efeitos = []
    for texto in agrupar_afixos(linhas[inicio:fim]):
        m_req = re.search(r"\(Requires Rank (\d+)\)", texto)
        if m_req and efeitos:
            efeitos[-1]["requer_rank"] = int(m_req.group(1))
        else:
            efeitos.append(estruturar_afixo(texto))
    return {
        "rank": int(m_rank.group(1)) if m_rank else None,
        "efeitos": efeitos,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/parser.py <imagem.png | texto.txt>")
        sys.exit(1)
    arquivo = Path(sys.argv[1])
    if arquivo.suffix == ".txt":
        texto = arquivo.read_text(encoding="utf-8")
    else:
        from ocr import ler_texto
        texto = ler_texto(arquivo)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(interpretar(texto), indent=2, ensure_ascii=False))
