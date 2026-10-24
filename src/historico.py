"""
Histórico dos itens avaliados: cada F8 vira uma linha em capturas/historico.jsonl.

O overlay (app.py) escreve; a janela principal (janela.py) lê. Os dois são
processos separados, então conversam por esse arquivo — simples e sem rede.
Uma linha por avaliação (JSON Lines): dá pra só acrescentar no fim, e uma
linha estragada (app fechado no meio da escrita) não estraga as outras.
"""

import json
from datetime import datetime
from pathlib import Path

from nucleo import PASTA_CAPTURAS, Avaliacao, Selo

ARQUIVO = PASTA_CAPTURAS / "historico.jsonl"


def registrar(av: Avaliacao, selo: Selo, arquivo: Path = ARQUIVO, com: str = "Todas") -> dict:
    """Acrescenta a avaliação no histórico e devolve o que foi gravado.
    `com` = com qual build o item foi avaliado ("Todas" ou o apelido)."""
    item = av.item or {}
    entrada = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "com": com,
        "titulo": selo.titulo,
        "qualidade": item.get("qualidade"),
        "tipo": item.get("tipo"),
        "slot": item.get("slot"),
        "serve": selo.serve,
        "parcial": selo.parcial,
        "linhas": [[[texto, estilo] for texto, estilo in linha] for linha in selo.linhas],
        "imagem": av.arquivo.name if av.arquivo else None,
        "erro": av.erro,
        "segundos": round(av.segundos, 2),
    }
    arquivo.parent.mkdir(exist_ok=True)
    with arquivo.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return entrada


def ler(limite: int = 50, arquivo: Path = ARQUIVO) -> list[dict]:
    """As últimas `limite` avaliações, da mais nova pra mais antiga."""
    if not arquivo.exists():
        return []
    entradas = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        try:
            entradas.append(json.loads(linha))
        except json.JSONDecodeError:
            continue  # linha cortada no meio: ignora só ela
    return entradas[::-1][:limite]
