"""
Gera o D3 Companion pra quem não tem Python, em dist/:
  - D3-Companion-Setup-<versão>.exe, o instalador (Inno Setup, ferramentas/instalador.iss);
  - D3-Companion-<versão>-windows.zip, a mesma pasta pra usar sem instalar.
O .exe mostra uma imagem de abertura na hora do clique (splash do PyInstaller).

    .venv\\Scripts\\activate
    pip install -r requirements-dev.txt
    python ferramentas/empacotar.py

O que entra no zip (pasta "D3 Companion"):
  - D3 Companion.exe e o Python/bibliotecas que ele usa (PyInstaller, modo pasta);
  - a página da janela (src/web). Builds não vão junto: cada um importa as suas;
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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from versao import VERSAO  # noqa: E402

NOME = "D3 Companion"
OBRA = RAIZ / "build"           # arquivos temporários do PyInstaller
SAIDA = RAIZ / "dist"
TESSERACT = Path(os.environ.get("TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR"))
# Inno Setup 6 (winget install JRSoftware.InnoSetup): onde o instalador dele costuma pôr.
ISCCS = [Path(os.environ.get(v, "")) / sub / "ISCC.exe" for v, sub in (
    ("LOCALAPPDATA", r"Programs\Inno Setup 6"), ("ProgramFiles(x86)", "Inno Setup 6"), ("ProgramFiles", "Inno Setup 6"))]


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


def gerar_abertura(destino: Path) -> Path:
    """A imagem que o .exe mostra na hora do clique, enquanto o Python carrega
    (splash do PyInstaller; a janela fecha ela quando aparece). Desenho próprio."""
    largura, altura = 480, 280
    img = Image.new("RGB", (largura, altura), (17, 18, 21))
    brilho = Image.new("RGB", img.size, (0, 0, 0))
    cx, cy = largura // 2, 112
    ImageDraw.Draw(brilho).polygon([(cx, cy - 50), (cx + 50, cy), (cx, cy + 50), (cx - 50, cy)], outline=(211, 58, 44), width=14)
    img = Image.blend(img, brilho.filter(ImageFilter.GaussianBlur(12)), 0.45)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, largura - 1, altura - 1), outline=(59, 62, 72), width=2)
    d.polygon([(cx, cy - 44), (cx + 44, cy), (cx, cy + 44), (cx - 44, cy)], outline=(226, 72, 56), width=8)
    d.polygon([(cx, cy - 16), (cx + 16, cy), (cx, cy + 16), (cx - 16, cy)], outline=(242, 196, 131), width=4)

    def fonte(nomes, tamanho):
        for nome in nomes:
            try:
                return ImageFont.truetype(nome, tamanho)
            except OSError:
                continue
        return ImageFont.load_default()

    for texto, y, f, cor in (("D3 COMPANION", 196, fonte(["segoeuib.ttf", "arialbd.ttf"], 24), (230, 230, 234)),
                             (f"v{VERSAO}", 234, fonte(["segoeui.ttf", "arial.ttf"], 14), (146, 149, 161))):
        x0, _, x1, _ = d.textbbox((0, 0), texto, font=f)
        d.text(((largura - (x1 - x0)) // 2, y), texto, font=f, fill=cor)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
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
    abertura = gerar_abertura(OBRA / "abertura.png")
    tesseract = OBRA / "tesseract"
    copiar_tesseract(tesseract)
    sep = os.pathsep
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--name", NOME, "--windowed", "--onedir", "--icon", str(icone), "--splash", str(abertura),
        "--paths", str(RAIZ / "src"),
        "--workpath", str(OBRA / "pyinstaller"), "--distpath", str(SAIDA), "--specpath", str(OBRA),
        "--add-data", f"{RAIZ / 'src' / 'web'}{sep}web",
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
    shutil.copy2(RAIZ / "LICENSE", pasta / "LICENSE.txt")
    arquivo = SAIDA / f"D3-Companion-{VERSAO}-windows.zip"
    arquivo.unlink(missing_ok=True)
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(pasta.rglob("*")):
            z.write(p, Path(NOME) / p.relative_to(pasta))
    print()
    for pronto in (arquivo, gerar_instalador(pasta, icone)):
        if pronto:
            soma = hashlib.sha256(pronto.read_bytes()).hexdigest()
            (SAIDA / f"{pronto.name}.sha256").write_text(f"{soma}  {pronto.name}\n", encoding="utf-8")
            print(f"Pronto: {pronto} ({pronto.stat().st_size / 2**20:.0f} MB)\nSHA-256: {soma}")
    return arquivo


def gerar_instalador(pasta: Path, icone: Path) -> Path | None:
    """O instalador (ferramentas/instalador.iss). Sem o Inno Setup, fica só o zip."""
    iscc = Path(os.environ["ISCC"]) if os.environ.get("ISCC") else next((p for p in ISCCS if p.is_file()), None)
    if iscc is None or not iscc.is_file():
        print("Sem o Inno Setup (ISCC.exe): só o zip. Instale com: winget install JRSoftware.InnoSetup")
        return None
    subprocess.run([str(iscc), "/Q", f"/DVersao={VERSAO}", f"/DPasta={pasta}", f"/DSaida={SAIDA}",
                    f"/DIcone={icone}", str(RAIZ / "ferramentas" / "instalador.iss")], check=True)
    return SAIDA / f"D3-Companion-Setup-{VERSAO}.exe"


if __name__ == "__main__":
    empacotar()
