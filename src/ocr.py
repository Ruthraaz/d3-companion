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

import sys
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

# No Windows o pytesseract não acha o Tesseract sozinho.
# Descomente a linha abaixo e ajuste o caminho se der erro "tesseract is not installed".
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def preprocessar(caminho: Path) -> Image.Image:
    """Prepara a imagem pro OCR.

    O Tesseract foi feito pra texto PRETO em fundo BRANCO (tipo página de livro).
    A dica do D3 é o contrário: texto colorido em fundo escuro, com letra pequena.
    Então fazemos 3 coisas:
      1. Aumentar a imagem 2x  -> letra pequena vira letra média.
      2. Tons de cinza         -> cor não importa pra ler, só o brilho.
      3. Inverter + limiarizar -> vira texto preto em fundo branco.
    """
    img = cv2.imread(str(caminho))
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    invertida = cv2.bitwise_not(cinza)
    # Otsu escolhe sozinho o melhor ponto de corte entre "texto" e "fundo".
    _, binaria = cv2.threshold(invertida, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binaria)


def ler_texto(caminho: Path, pre: bool = False) -> str:
    imagem = preprocessar(caminho) if pre else Image.open(caminho)
    # --psm 6 = "trate a imagem como um bloco de texto uniforme" (bom pra dicas).
    return pytesseract.image_to_string(imagem, lang="eng", config="--psm 6")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/ocr.py <imagem> [--pre]")
        sys.exit(1)
    arquivo = Path(sys.argv[1])
    print(ler_texto(arquivo, pre="--pre" in sys.argv))
