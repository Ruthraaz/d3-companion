"""
Gera o D3 Companion pra quem não tem Python: dist/D3-Companion-<versão>-windows.zip.

    .venv\\Scripts\\activate
    pip install -r requirements-dev.txt
    python ferramentas/empacotar.py

O que entra no zip (pasta "D3 Companion"):
  - D3 Companion.exe e o Python/bibliotecas que ele usa (PyInstaller, modo pasta);
  - a página da janela (src/web) e as builds de exemplo (builds/);
  - o Tesseract (OCR) só com o que o tesseract.exe usa + o inglês, e a licença dele.

Do seu PC não entra nada: nem .env, nem capturas/, nem dados/ (o app cria
tudo em %APPDATA%\\D3 Companion na primeira vez).
"""

import hashlib
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from versao import VERSAO  # noqa: E402

NOME = "D3 Companion"
OBRA = RAIZ / "build"           # arquivos temporários do PyInstaller
SAIDA = RAIZ / "dist"
TESSERACT = Path(os.environ.get("TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR"))


# ------------------------------------------------------------ ícone (desenho próprio)

def gerar_icone(destino: Path) -> Path:
    """A runa do app: losango vermelho com brilho, num quadrado escuro."""
    tamanho = 256
    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=48, fill=(17, 18, 21, 255))
    brilho = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(brilho).polygon([(128, 40), (216, 128), (128, 216), (40, 128)], outline=(211, 58, 44, 255), width=26)
    img.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(14)))
    d.polygon([(128, 52), (204, 128), (128, 204), (52, 128)], outline=(226, 72, 56, 255), width=16)
    d.polygon([(128, 98), (158, 128), (128, 158), (98, 128)], outline=(242, 196, 131, 255), width=8)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return destino


# ------------------------------------------------------------ Tesseract mínimo

def _imports(arquivo: Path) -> list[str]:
    """DLLs que um .exe/.dll do Windows pede (tabela de imports do PE)."""
    d = arquivo.read_bytes()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    n_secoes = struct.unpack_from("<H", d, pe + 6)[0]
    tam_opc = struct.unpack_from("<H", d, pe + 20)[0]
    opc = pe + 24
    dirs = opc + (112 if struct.unpack_from("<H", d, opc)[0] == 0x20B else 96)
    rva = struct.unpack_from("<I", d, dirs + 8)[0]
    secoes = [struct.unpack_from("<8sIIII", d, opc + tam_opc + 40 * i) for i in range(n_secoes)]

    def deslocamento(r):
        for _, vsize, va, rsize, raw in secoes:
            if va <= r < va + max(vsize, rsize):
                return r - va + raw
        return None

    nomes, p = [], deslocamento(rva)
    while p is not None:
        campos = struct.unpack_from("<IIIII", d, p)
        if not any(campos):
            break
        o = deslocamento(campos[3])
        nomes.append(d[o:d.index(b"\0", o)].decode())
        p += 20
    return nomes


def copiar_tesseract(destino: Path) -> None:
    """Só o tesseract.exe, as DLLs que ele usa de verdade, o inglês e a licença."""
    if not (TESSERACT / "tesseract.exe").exists():
        sys.exit(f"Não achei o Tesseract em {TESSERACT}. Instale ou defina TESSERACT_DIR.")
    locais = {p.name.lower(): p for p in TESSERACT.glob("*.dll")}
    falta, usadas = [TESSERACT / "tesseract.exe"], set()
    while falta:
        for dep in _imports(falta.pop()):
            if dep.lower() in locais and dep.lower() not in usadas:
                usadas.add(dep.lower())
                falta.append(locais[dep.lower()])
    shutil.rmtree(destino, ignore_errors=True)
    (destino / "tessdata").mkdir(parents=True)
    shutil.copy2(TESSERACT / "tesseract.exe", destino)
    for nome in usadas:
        shutil.copy2(locais[nome], destino)
    shutil.copy2(TESSERACT / "tessdata" / "eng.traineddata", destino / "tessdata")
    for pasta in ("configs", "tessconfigs"):
        if (TESSERACT / "tessdata" / pasta).is_dir():
            shutil.copytree(TESSERACT / "tessdata" / pasta, destino / "tessdata" / pasta)
    shutil.copy2(TESSERACT / "doc" / "LICENSE", destino / "LICENSE-tesseract.txt")
    print(f"Tesseract: {len(usadas)} DLLs de {len(locais)}")


# ------------------------------------------------------------ PyInstaller e zip

def empacotar() -> Path:
    icone = gerar_icone(OBRA / "icone.ico")
    tesseract = OBRA / "tesseract"
    copiar_tesseract(tesseract)
    sep = os.pathsep
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--name", NOME, "--windowed", "--onedir", "--icon", str(icone),
        "--paths", str(RAIZ / "src"),
        "--workpath", str(OBRA / "pyinstaller"), "--distpath", str(SAIDA), "--specpath", str(OBRA),
        "--add-data", f"{RAIZ / 'src' / 'web'}{sep}web",
        "--add-data", f"{RAIZ / 'builds'}{sep}builds",
        # O overlay e a janela são carregados por import dentro do main: avisa o PyInstaller.
        "--hidden-import", "app", "--hidden-import", "janela",
        "--exclude-module", "tkinter", "--exclude-module", "unittest",
        str(RAIZ / "src" / "d3companion.py"),
    ], check=True)

    pasta = SAIDA / NOME
    # O Tesseract entra depois: com --add-data o PyInstaller acha as DLLs dele e
    # copia de novo na pasta principal (mais de 100 MB repetidos).
    shutil.copytree(tesseract, pasta / "_internal" / "tesseract")
    shutil.copy2(RAIZ / "LEIA-ME.txt", pasta / "LEIA-ME.txt")
    arquivo = SAIDA / f"D3-Companion-{VERSAO}-windows.zip"
    arquivo.unlink(missing_ok=True)
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(pasta.rglob("*")):
            z.write(p, Path(NOME) / p.relative_to(pasta))
    soma = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    (SAIDA / f"{arquivo.name}.sha256").write_text(f"{soma}  {arquivo.name}\n", encoding="utf-8")
    print(f"\nPronto: {arquivo} ({arquivo.stat().st_size / 2**20:.0f} MB)\nSHA-256: {soma}")
    return arquivo


if __name__ == "__main__":
    empacotar()
