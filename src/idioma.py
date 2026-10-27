"""
Inglês ou português no Python (selo do overlay e mensagens que vão pra janela).

O mesmo esquema da janela (src/web/idioma.js): o texto no código é em português
e src/web/dados/en.json diz como fica em inglês.

    t("Precisa ser Ancient")              -> "Must be Ancient" (inglês) ou o próprio texto
    t("A build pede: {itens}", itens=x)   -> "The build asks for: x"

O idioma vem das Configurações (IDIOMA no .env; vazio = o do Windows). Quando o
.env muda, a próxima frase já sai no idioma novo (a janela troca sem reiniciar;
o overlay é reiniciado pela janela ao salvar).
"""

import json
import os
from functools import lru_cache

from pastas import ARQUIVO_ENV, WEB

EN_JSON = WEB / "dados" / "en.json"

_lido = {"quando": None, "idioma": "pt"}


@lru_cache(maxsize=1)
def _frases() -> dict[str, str]:
    try:
        dados = json.loads(EN_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}  # sem o arquivo: tudo em português
    return {k: v for k, v in dados.items() if isinstance(k, str) and isinstance(v, str)}


def atual() -> str:
    """ "en" ou "pt". Relê o .env só quando ele mudou. D3C_IDIOMA no ambiente
    manda mais que tudo (os testes usam pra conferir as mensagens em português)."""
    if os.environ.get("D3C_IDIOMA") in ("en", "pt"):
        return os.environ["D3C_IDIOMA"]
    try:
        quando = ARQUIVO_ENV.stat().st_mtime if ARQUIVO_ENV.exists() else 0
    except OSError:
        quando = 0
    if quando != _lido["quando"]:
        from config import ler_config  # aqui: config importa coisas que usam t()
        _lido.update(quando=quando, idioma=ler_config()["IDIOMA"])
    return _lido["idioma"]


def t(texto: str, **vars) -> str:
    """A frase no idioma escolhido, com {nome} trocado pelos valores."""
    frase = _frases().get(texto, texto) if atual() == "en" else texto
    return frase.format_map(_Sobra(vars)) if vars else frase


class _Sobra(dict):
    """Variável que falta fica como {nome} (em vez de quebrar a mensagem)."""

    def __missing__(self, chave):
        return "{" + chave + "}"
