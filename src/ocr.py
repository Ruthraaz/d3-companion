"""
Etapa 1 — OCR de uma dica de item (tooltip) salva em arquivo.

Objetivo: descobrir se o Tesseract consegue ler as dicas do Diablo 3
ANTES de construir o resto do app. Se o OCR não ler bem, nada adianta.

Uso:
    python src/ocr.py samples/lendario_cloak_garwulf.png
    python src/ocr.py samples/lendario_cloak_garwulf.png --pre   (com pré-processamento)

Resultado do primeiro teste (24/10/2026): a imagem CRUA leu os números melhor.
O pré-processamento (Otsu) apagou partes de textos finos, ex.: "-0.5% Damage"
virou "-C.2°. Damage". Por isso o padrão é ler cru, e o pré-processamento
fica como opção pra gente melhorar depois.
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from dotenv import load_dotenv
from PIL import Image

# No Windows o pytesseract não acha o Tesseract sozinho.
# O caminho vem do .env (TESSERACT_CMD, veja .env.example); sem ele,
# usamos o caminho padrão do instalador da UB Mannheim.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def preprocessar(imagem: Image.Image) -> Image.Image:
    """Prepara a imagem pro OCR.

    O Tesseract foi feito pra texto PRETO em fundo BRANCO (tipo página de livro).
    A dica do D3 é o contrário: texto colorido em fundo escuro, com letra pequena.
    Então fazemos 3 coisas:
      1. Aumentar a imagem 2x  -> letra pequena vira letra média.
      2. Tons de cinza         -> cor não importa pra ler, só o brilho.
      3. Inverter + limiarizar -> vira texto preto em fundo branco.
    """
    img = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    invertida = cv2.bitwise_not(cinza)
    # Otsu escolhe sozinho o melhor ponto de corte entre "texto" e "fundo".
    _, binaria = cv2.threshold(invertida, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binaria)


def ler_texto(origem: Path | Image.Image, pre: bool = False, ampliar: int = 1) -> str:
    """Lê o texto de um arquivo de imagem ou de uma imagem já na memória
    (a captura da Etapa 4 entrega a imagem direto, sem salvar).

    ampliar=2 aumenta a imagem antes do OCR (a letra da dica é pequena).
    """
    imagem = origem if isinstance(origem, Image.Image) else Image.open(origem)
    if ampliar != 1:
        imagem = imagem.convert("RGB").resize(
            (imagem.width * ampliar, imagem.height * ampliar), Image.LANCZOS)
    if pre:
        imagem = preprocessar(imagem)
    # --psm 6 = "trate a imagem como um bloco de texto uniforme" (bom pra dicas).
    return pytesseract.image_to_string(imagem, lang="eng", config="--psm 6")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/ocr.py <imagem> [--pre]")
        sys.exit(1)
    arquivo = Path(sys.argv[1])
    print(ler_texto(arquivo, pre="--pre" in sys.argv))
