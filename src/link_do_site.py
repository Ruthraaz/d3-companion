"""
Build montada no site (docs/montar.html) -> build do app.

O site põe a build no próprio link, depois do "#":
    https://ruthraaz.github.io/d3-companion/montar.html#b=<JSON comprimido, base64url>

O link vem de fora (colado pela pessoa), então tudo é conferido: só o endereço
do site, tamanho máximo antes e depois de abrir (nada de "bomba" de compressão),
JSON de objeto e, no fim, a mesma conferência das builds do app (problemas_da_build).
"""

import base64
import binascii
import json
import re
import urllib.parse
import zlib

from idioma import t

HOST = "ruthraaz.github.io"
CAMINHOS = {"/d3-companion/montar.html", "/d3-companion/montar"}
MAXIMO_DO_LINK = 20_000      # caracteres depois de "#b="
MAXIMO_ABERTO = 200_000      # bytes do JSON depois de descomprimir


class ErroLinkDoSite(ValueError):
    pass


def e_link_do_site(texto: str) -> bool:
    try:
        partes = urllib.parse.urlsplit((texto or "").strip())
    except ValueError:
        return False
    return partes.netloc.lower() == HOST and partes.path in CAMINHOS


def build_do_link(texto: str) -> dict:
    """O link do site -> build no formato do app (sem gravar). ErroLinkDoSite se não der."""
    texto = (texto or "").strip()
    if len(texto) > MAXIMO_DO_LINK + 200 or any(c.isspace() for c in texto):
        raise ErroLinkDoSite(t("Esse link está estranho (grande demais ou com espaço no meio). Copie de novo no site."))
    partes = urllib.parse.urlsplit(texto)
    if partes.scheme != "https" or partes.netloc.lower() != HOST or partes.path not in CAMINHOS:
        raise ErroLinkDoSite(t("Esse link não é do site do D3 Companion."))
    m = re.fullmatch(r"b=([A-Za-z0-9_-]{1,%d})" % MAXIMO_DO_LINK, partes.fragment)
    if not m:
        raise ErroLinkDoSite(t("O link não tem a build. No site, use \"Copiar link da build\"."))
    try:
        cru = base64.urlsafe_b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4))
        abrir = zlib.decompressobj(-15)  # deflate "cru", como o CompressionStream("deflate-raw") do site
        aberto = abrir.decompress(cru, MAXIMO_ABERTO)
        if abrir.unconsumed_tail or not abrir.eof:
            raise ErroLinkDoSite(t("A build desse link é grande demais ou veio cortada."))
        build = json.loads(aberto.decode("utf-8"))
    except (binascii.Error, zlib.error, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ErroLinkDoSite(t("Não consegui abrir a build desse link (ele pode ter sido cortado ao copiar).")) from e
    if not isinstance(build, dict):
        raise ErroLinkDoSite(t("Não consegui abrir a build desse link."))
    return build_montada(build, "A build do link tem problema: ")


def build_montada(build, aviso: str = "A build tem problema: ") -> dict:
    """Build feita no "Montar build" (do link do site ou da aba Montar do app),
    conferida como qualquer coisa que vem de fora. ErroLinkDoSite se não serve."""
    from avaliador import problemas_da_build

    if not isinstance(build, dict):
        raise ErroLinkDoSite(t("Isso não é uma build."))
    build = dict(build)
    build["fonte"] = {"site": "montar"}  # quem manda não escolhe a fonte
    for chave in [k for k in build if k == "id" or k.startswith("_")]:
        del build[chave]  # comentário ("_...") e id não vêm de fora
    nome = build.get("nome") if isinstance(build.get("nome"), str) else ""
    apelido = build.get("apelido") if isinstance(build.get("apelido"), str) else nome
    build["nome"], build["apelido"] = nome.strip()[:80], (apelido.strip() or nome.strip())[:40]
    problemas = problemas_da_build(build)
    if problemas:
        raise ErroLinkDoSite(aviso + " ".join(problemas[:3]))
    return build
