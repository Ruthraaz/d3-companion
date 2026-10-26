"""
Cuidados com a internet: respostas com limite de tamanho e links que o app abre.

Sem limite, um site com problema (ou alguém no meio do caminho) poderia mandar
um arquivo enorme e travar o app enchendo a memória. O maior arquivo que o app
baixa de verdade é o data.json do planejador do Maxroll, com ~1,3 MB.
"""

import urllib.parse

MAXIMO = 20 * 1024 * 1024  # 20 MB


class RespostaGrande(ValueError):
    """A resposta passou do limite: o app não lê o resto."""


def ler(resposta, maximo: int | None = None) -> bytes:
    """Lê a resposta inteira, mas no máximo `maximo` bytes (padrão: MAXIMO)."""
    maximo = MAXIMO if maximo is None else maximo
    dados = resposta.read(maximo + 1)
    if len(dados) > maximo:
        raise RespostaGrande(f"Resposta maior que {maximo // (1024 * 1024)} MB.")
    return dados


def link_seguro(url) -> bool:
    """Só https://maxroll.gg/..., sem usuário/senha, porta, espaço ou caractere de
    controle: o Windows abre o endereço com o programa padrão, então nada de truque."""
    if not isinstance(url, str) or len(url) > 500 or any(c.isspace() or ord(c) < 32 for c in url):
        return False
    partes = urllib.parse.urlsplit(url)
    return partes.scheme == "https" and partes.netloc == "maxroll.gg"
