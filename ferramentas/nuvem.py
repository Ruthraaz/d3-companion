"""
Liga (ou desliga) a nuvem do montador do site: preenche docs/config-nuvem.js e
libera o endereço do projeto Supabase no connect-src da CSP do docs/montar.html.

Só aceita a chave PÚBLICA do Supabase ("publishable" sb_publishable_... ou o JWT
"anon"). Ela é feita pra ficar no site; quem protege os dados é o RLS
(ferramentas/supabase.sql). A service_role / secret é recusada.

Rodar (na pasta do projeto):
    python ferramentas/nuvem.py https://SEU-PROJETO.supabase.co SUA_CHAVE_PUBLICA
    python ferramentas/nuvem.py --desligar
Depois: rode os testes, faça commit e push (o GitHub Pages publica sozinho).
"""

import base64
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
URL = re.compile(r"^https://[a-z0-9-]+\.supabase\.co$")
CONFIG = re.compile(r'window\.D3C_NUVEM = \{ url: "([^"]*)", chave: "([^"]*)" \};')
CSP_CONNECT = re.compile(r"connect-src [^;\"]*")


class ErroNuvem(ValueError):
    pass


def papel_da_chave(chave: str) -> str:
    """"publishable", "anon", "secreta" (service_role / sb_secret_) ou "" (não é chave)."""
    if re.fullmatch(r"sb_publishable_[\w-]+", chave):
        return "publishable"
    if chave.startswith("sb_secret_"):
        return "secreta"
    partes = chave.split(".")
    if len(partes) != 3:
        return ""
    try:
        dados = json.loads(base64.urlsafe_b64decode(partes[1] + "=" * (-len(partes[1]) % 4)))
    except ValueError:
        return ""
    papel = dados.get("role") if isinstance(dados, dict) else None
    return "anon" if papel == "anon" else "secreta" if papel else ""


def conferir(url: str, chave: str) -> tuple[str, str]:
    url, chave = url.strip().rstrip("/"), chave.strip()
    if not URL.match(url):
        raise ErroNuvem("O endereço tem que ser o 'Project URL' do Supabase: https://<projeto>.supabase.co")
    papel = papel_da_chave(chave)
    if papel == "secreta":
        raise ErroNuvem("Essa é a chave SECRETA (service_role / sb_secret_). Ela nunca vai no site nem no Git. "
                        "Use a 'anon' ou 'publishable'. Se ela vazou, gere outra no painel do Supabase.")
    if papel not in ("anon", "publishable"):
        raise ErroNuvem("Isso não parece a chave pública do Supabase (anon eyJ... ou sb_publishable_...).")
    return url, chave


def connect_src(url: str) -> str:
    return f"connect-src 'self' {url}" if url else "connect-src 'self'"


def gravar(url: str, chave: str, docs: Path = DOCS) -> None:
    """url/chave vazios = desliga."""
    config = docs / "config-nuvem.js"
    texto = config.read_text(encoding="utf-8")
    if not CONFIG.search(texto):
        raise ErroNuvem("Não achei a linha window.D3C_NUVEM = { url: \"\", chave: \"\" }; no config-nuvem.js")
    config.write_text(CONFIG.sub(lambda _: f'window.D3C_NUVEM = {{ url: "{url}", chave: "{chave}" }};', texto),
                      encoding="utf-8", newline="\n")
    pagina = docs / "montar.html"
    html = pagina.read_text(encoding="utf-8")
    if len(CSP_CONNECT.findall(html)) != 1:
        raise ErroNuvem("Não achei o connect-src (um só) na CSP do montar.html")
    pagina.write_text(CSP_CONNECT.sub(connect_src(url), html), encoding="utf-8", newline="\n")


def config_atual(docs: Path = DOCS) -> tuple[str, str]:
    achado = CONFIG.search((docs / "config-nuvem.js").read_text(encoding="utf-8"))
    return (achado.group(1), achado.group(2)) if achado else ("", "")


def main():
    if sys.argv[1:] == ["--desligar"]:
        gravar("", "")
        print("Nuvem desligada: config-nuvem.js vazio e o connect-src voltou a 'self'.")
        return
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    try:
        url, chave = conferir(sys.argv[1], sys.argv[2])
        gravar(url, chave)
    except ErroNuvem as erro:
        print(f"Erro: {erro}")
        sys.exit(1)
    print(f"Nuvem ligada em {url} (chave pública, {len(chave)} caracteres).")
    print("Agora: rode os testes, faça commit de docs/config-nuvem.js e docs/montar.html e dê push.")


if __name__ == "__main__":
    main()
