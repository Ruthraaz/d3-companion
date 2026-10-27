"""
Atualização do app: confere no GitHub se saiu versão nova e instala sozinho.

  1. versao_nova(): pergunta à API de Releases do GitHub qual é a última
     versão. Se for maior que VERSAO, diz qual é e onde está o instalador;
  2. baixar(): baixa o D3-Companion-Setup-X.exe da Release pra uma pasta
     temporária e confere o tamanho e o SHA-256 (o GitHub informa o "digest"
     de cada arquivo). Veio diferente? Apaga e não instala;
  3. instalar(): espera uns segundos (o tempo do app fechar), roda o instalador
     sem perguntas (/SILENT, só a barra de progresso) e ele abre o app de novo.

Só baixa de https://github.com/Ruthraaz/d3-companion/releases/download/...;
nenhum endereço que venha de fora é aberto.
Só instala sozinho no app instalado (tem unins000.exe ao lado do .exe). Do zip
ou do código, o botão abre a página da Release.

Uso:
    python src/atualizar.py     # mostra se tem versão nova (não baixa nada)
"""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from idioma import t
from pastas import NO_EXE
from rede import ler
from versao import VERSAO

REPO = "Ruthraaz/d3-companion"
URL_ULTIMA = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA_DA_ULTIMA = f"https://github.com/{REPO}/releases/latest"
PREFIXO_DOWNLOAD = f"https://github.com/{REPO}/releases/download/"
NOME_DO_INSTALADOR = re.compile(r"^D3-Companion-Setup-(\d+\.\d+\.\d+)\.exe$")
MAXIMO_DO_INSTALADOR = 400 * 1024 * 1024  # o de hoje tem ~90 MB
PASTA_DO_DOWNLOAD = Path(tempfile.gettempdir()) / "D3Companion-atualizacao"
PEDACO = 1024 * 1024


class ErroAtualizacao(Exception):
    """Erro com mensagem pronta pra mostrar na tela."""


def numero(versao: str) -> tuple[int, ...] | None:
    """"v1.0.10" -> (1, 0, 10); None se não for nesse formato."""
    m = re.fullmatch(r"v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})", versao or "")
    return tuple(int(x) for x in m.groups()) if m else None


def instalado() -> bool:
    """O app veio do instalador (e não do zip nem do código)."""
    return NO_EXE and (Path(sys.executable).parent / "unins000.exe").exists()


def versao_nova(abrir=urllib.request.urlopen, atual: str = VERSAO) -> dict | None:
    """A última Release, se for mais nova que a atual: {"versao", "instalador":
    {"url", "nome", "sha256", "tamanho"} ou None}. Sem internet ou resposta
    estranha: None (não atrapalha quem só quer usar o app)."""
    pedido = urllib.request.Request(URL_ULTIMA, headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"D3-Companion/{atual}"})
    try:
        with abrir(pedido, timeout=15) as r:
            dados = json.loads(ler(r, maximo=2 * 1024 * 1024))
        versao = numero(dados["tag_name"])
    except Exception:  # noqa: BLE001 — qualquer problema aqui só esconde a faixa
        return None
    if versao is None or dados.get("draft") or dados.get("prerelease") or versao <= (numero(atual) or ()):
        return None
    texto = ".".join(map(str, versao))
    instalador = None
    for arquivo in dados.get("assets") or []:
        m = NOME_DO_INSTALADOR.match(str(arquivo.get("name", "")))
        url, digest = str(arquivo.get("browser_download_url", "")), str(arquivo.get("digest") or "")
        if (m and m.group(1) == texto and url == f"{PREFIXO_DOWNLOAD}v{texto}/{arquivo['name']}"
                and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                and 0 < int(arquivo.get("size") or 0) <= MAXIMO_DO_INSTALADOR):
            instalador = {"url": url, "nome": arquivo["name"], "sha256": digest[7:], "tamanho": int(arquivo["size"])}
    return {"versao": texto, "instalador": instalador}


def baixar(instalador: dict, pasta: Path = PASTA_DO_DOWNLOAD, abrir=urllib.request.urlopen,
           progresso=lambda fracao: None) -> Path:
    """Baixa o instalador e confere tamanho e SHA-256. Devolve o caminho do .exe."""
    if not instalador["url"].startswith(PREFIXO_DOWNLOAD) or not NOME_DO_INSTALADOR.match(instalador["nome"]):
        raise ErroAtualizacao(t("Endereço da atualização estranho; não baixei."))
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.glob("D3-Companion-Setup-*.exe"):  # restos de atualizações anteriores
        velho.unlink(missing_ok=True)
    destino = pasta / instalador["nome"]
    soma, recebidos = hashlib.sha256(), 0
    pedido = urllib.request.Request(instalador["url"], headers={"User-Agent": f"D3-Companion/{VERSAO}"})
    try:
        with abrir(pedido, timeout=30) as r, open(destino, "wb") as saida:
            while pedaco := r.read(PEDACO):
                recebidos += len(pedaco)
                if recebidos > instalador["tamanho"]:
                    break
                soma.update(pedaco)
                saida.write(pedaco)
                progresso(recebidos / instalador["tamanho"])
    except OSError as e:  # sem internet, disco cheio...
        destino.unlink(missing_ok=True)
        raise ErroAtualizacao(t("Não consegui baixar a atualização. Está sem internet?")) from e
    if recebidos != instalador["tamanho"] or soma.hexdigest() != instalador["sha256"]:
        destino.unlink(missing_ok=True)
        raise ErroAtualizacao(t("O arquivo baixado veio diferente do publicado; não instalei. Tente de novo."))
    return destino


def comando_de_instalar(arquivo: Path) -> str:
    """Espera ~3 s (o app fecha nesse meio-tempo) e roda o instalador sem perguntas.
    O instalador abre o app de novo no fim (instalador.iss, [Run] com WizardSilent)."""
    return f'cmd /c ping -n 4 127.0.0.1 >nul & "{arquivo}" /SILENT /SUPPRESSMSGBOXES /NORESTART'


def instalar(arquivo: Path, executar=subprocess.Popen) -> None:
    executar(comando_de_instalar(arquivo), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    nova = versao_nova()
    if not nova:
        print(f"Você está na última versão ({VERSAO}) ou sem internet.")
    else:
        print(f"Versão nova: {nova['versao']} (você tem {VERSAO}). Instalador: "
              + (nova["instalador"]["nome"] if nova["instalador"] else "não achei na Release"))


if __name__ == "__main__":
    main()
