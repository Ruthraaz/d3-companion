"""
Gera as imagens de divulgação do site (docs/img/):

    janela.png        a janela do app em inglês (aba Montar, com a dica de um item aberta)
    janela.pt.png     a mesma, em português (página docs/pt/)
    compartilhar.png  a imagem que aparece quando o link é compartilhado (1200x630, em inglês)

    python ferramentas/vitrine.py

A janela é a do modo de exemplo (sem Python, com builds de exemplo), aberta num
Edge sem tela (--headless) a partir de uma CÓPIA de src/web numa pasta
temporária: lá entram vitrine.css (esconde as imagens: nada de ícone ou arte da
Blizzard no site) e vitrine.js (abre a aba Montar e mostra a dica). O app de
verdade não muda. Não tira print da tela do PC: o Edge desenha a página sozinho.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "src" / "web"
DESTINO = RAIZ / "docs" / "img"
EDGES = [Path(os.environ.get(v, "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
         for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]

VITRINE_CSS = """
img { visibility: hidden !important; }
.abertura { display: none !important; }
* { animation: none !important; transition: none !important; }
"""

# Roda depois que o modo de exemplo abriu: copia uma build pro montador e abre a dica.
VITRINE_JS = """
(async () => {
  const esperar = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 50 && !(window.estado && estado.builds.length); i++) await esperar(100);
  const t = s => window.Idioma.t(s);
  const botao = [...document.querySelectorAll("#cabeca-build button")].find(b => b.textContent === t("Copiar pro montador"));
  if (botao) botao.click();
  await esperar(800);
  const m = document.getElementById("painel-montar");
  const nome = m.querySelector(".nome-da-build");
  if (nome) { nome.value = window.Idioma.atual === "en" ? "My Demon Hunter build" : "Minha build de Caçador"; nome.dispatchEvent(new Event("input")); }
  const peito = [...m.querySelectorAll(".espaco[data-dica]")][2];
  if (peito) { peito.click(); await esperar(300); }
  const dica = () => document.querySelector(".dica-item");
  for (let i = 0; i < 40 && !(dica() && !dica().hidden); i++) {
    const alvo = [...m.querySelectorAll(".espaco[data-dica]")][2];
    if (alvo) { alvo.dispatchEvent(new MouseEvent("mouseout", { bubbles: true }));
                document.body.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
                alvo.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); }
    await esperar(250);
  }
})();
"""


def edge() -> Path:
    for caminho in EDGES:
        if caminho.is_file():
            return caminho
    sys.exit("Não achei o Microsoft Edge (msedge.exe).")


def print_da_janela(arquivo: Path, idioma: str, largura=1280, altura=800):
    """idioma: "en" ou "pt" (o app escolhe pelo idioma do navegador, que o --lang troca)."""
    with tempfile.TemporaryDirectory() as pasta:
        copia = Path(pasta) / "web"
        shutil.copytree(WEB, copia)
        pagina = copia / "index.html"
        html = pagina.read_text(encoding="utf-8")
        # Só na cópia: sem a CSP (em file:// ela barraria os próprios arquivos) e com a vitrine.
        html = re.sub(r'\s*<meta http-equiv="Content-Security-Policy"[^>]*>', "", html, flags=re.S)
        html = html.replace("</head>", '  <link rel="stylesheet" href="vitrine.css">\n</head>')
        html = html.replace('<script src="app.js"></script>', '<script src="app.js"></script>\n  <script src="vitrine.js"></script>')
        pagina.write_text(html, encoding="utf-8")
        (copia / "vitrine.css").write_text(VITRINE_CSS, encoding="utf-8")
        (copia / "vitrine.js").write_text(VITRINE_JS, encoding="utf-8")
        subprocess.run([str(edge()), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--allow-file-access-from-files", f"--user-data-dir={Path(pasta) / 'perfil'}",
                        "--no-first-run", "--disable-extensions", f"--lang={'pt-BR' if idioma == 'pt' else 'en-US'}", "--virtual-time-budget=20000",
                        f"--window-size={largura},{altura}", f"--screenshot={arquivo}", pagina.as_uri()],
                       check=True, capture_output=True, timeout=120)


def fonte(nomes: list[str], tamanho: int):
    for nome in nomes:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def imagem_de_compartilhar(janela: Path, arquivo: Path):
    """1200x630: título e frase à esquerda, um pedaço da janela à direita. Desenho
    próprio (fundo grafite, losango vermelho), nada da arte do jogo."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#111215")
    d = ImageDraw.Draw(img)
    for x in range(W):  # brilho vermelho bem fraco no canto
        d.line([(x, 0), (x, H)], fill=(17 + max(0, 30 - x // 20), 18, 21))
    tela = Image.open(janela).convert("RGB")
    tela = tela.crop((0, 0, min(tela.width, 1100), min(tela.height, 760)))
    tela.thumbnail((640, 470))
    x0, y0 = W - tela.width - 40, (H - tela.height) // 2
    d.rectangle([x0 - 2, y0 - 2, x0 + tela.width + 1, y0 + tela.height + 1], outline="#3b3e48", width=2)
    img.paste(tela, (x0, y0))
    # Losango (o símbolo do app).
    cx, cy, r = 80, 112, 22
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], outline="#d33a2c", width=5)
    serifa = ["pala.ttf", "palab.ttf", "georgia.ttf"]
    sans = ["segoeui.ttf", "arial.ttf"]
    d.text((116, 92), "D3 COMPANION", font=fonte(["segoeuib.ttf", "arialbd.ttf"], 30), fill="#e6e6ea")
    d.text((56, 180), "Know right away if an", font=fonte(serifa, 46), fill="#f2c483")
    d.text((56, 236), "item fits your build.", font=fonte(serifa, 46), fill="#f2c483")
    linhas = ["Press F8 in Diablo III and see what", "the item has and what it's missing.",
              "Plan builds in the app or online."]
    for i, linha in enumerate(linhas):
        d.text((56, 320 + i * 36), linha, font=fonte(sans, 26), fill="#c9cad1")
    d.rounded_rectangle([56, 470, 470, 524], radius=8, fill="#d33a2c")
    d.text((76, 480), "Free · Windows · Open source", font=fonte(["segoeuib.ttf", "arialbd.ttf"], 24), fill="#ffffff")
    d.text((56, 560), "ruthraaz.github.io/d3-companion", font=fonte(sans, 22), fill="#9295a1")
    img.save(arquivo, optimize=True)


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for idioma, nome in (("en", "janela.png"), ("pt", "janela.pt.png")):
        janela = DESTINO / nome
        print_da_janela(janela, idioma)
        Image.open(janela).convert("RGB").save(janela, optimize=True)
    imagem_de_compartilhar(DESTINO / "janela.png", DESTINO / "compartilhar.png")
    for nome in ("janela.png", "janela.pt.png", "compartilhar.png"):
        print(f"Pronto: docs/img/{nome} ({(DESTINO / nome).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
