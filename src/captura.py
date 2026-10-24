"""
Etapa 4 — Captura da dica (tooltip) perto do cursor.

Duas partes:
  - capturar_perto_do_cursor(): print de uma faixa da tela em volta do mouse.
  - recortar_dica(): acha a dica dentro do print e recorta só ela.

Como a dica é achada (descoberto testando nos prints de samples/):
  O interior da dica é quase PRETO PURO (valores 0-4), e as bordas da
  esquerda e da direita são linhas claras que vão de cima a baixo sem
  interrupção. Então procuramos um PAR de colunas com linhas claras longas
  e da mesma altura, com o miolo entre elas majoritariamente preto.
  Por que não só "a maior área preta"? Porque o fundo do jogo e as grades
  do inventário encostam na dica e a área "vaza" pra tela toda.

O app só OLHA a tela (print), nada de ler memória do jogo.
"""

import ctypes
import ctypes.wintypes
import sys

import cv2
import numpy as np
from PIL import Image, ImageGrab

CLARO = 25          # pixel com algum canal >= 25 conta como "claro" (borda)
ESCURO = 12         # todos os canais < 12 conta como "preto" (miolo da dica)
ALTURA_MINIMA = 250        # borda vertical precisa ter pelo menos isso
LARGURA = (300, 900)       # largura possível da dica, em pixels
MIOLO_PRETO = 0.55         # fração mínima de preto entre as bordas
DISTANCIA_DO_CURSOR = 250  # a dica aparece ao lado do item sob o mouse
MEIA_LARGURA_CAPTURA = 1100
FOLGA_TOPO, FOLGA_BASE = 70, 10  # o título fica acima das bordas laterais
AMPLIAR = 2                      # letra pequena: o OCR lê melhor ampliada


def _maior_sequencia(coluna: np.ndarray) -> tuple[int, int]:
    """(início, tamanho) da maior sequência de True numa coluna."""
    d = np.diff(np.concatenate(([0], coluna.astype(np.int8), [0])))
    inicios, fins = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    if len(inicios) == 0:
        return 0, 0
    i = int(np.argmax(fins - inicios))
    return int(inicios[i]), int(fins[i] - inicios[i])


VIZINHOS = (3, 13)       # janela "ao lado" da borda, em px pra dentro da dica
VIZINHOS_PRETOS = 7      # quantos desses 10 precisam ser pretos
VAO = (1, 7)             # o vão estreito logo depois da borda (só no topo)
VAO_PRETOS = 3           # quantos desses 6 precisam ser pretos
_TAPAR = np.ones((9, 1), np.uint8)  # buraco vertical que ainda é a mesma borda


def _pretos_ao_lado(escuro: np.ndarray, janela: tuple[int, int], miolo_a_direita: bool
                    ) -> np.ndarray:
    """Quantos pixels pretos há em x+a .. x+b-1 (ou x-b+1 .. x-a, espelhado)."""
    altura, largura = escuro.shape
    acumulado = np.zeros((altura, largura + 1), np.int32)
    np.cumsum(escuro, axis=1, out=acumulado[:, 1:])
    a, b = janela
    contagem = np.zeros((altura, largura), np.int32)
    if miolo_a_direita:
        contagem[:, :largura - b] = acumulado[:, b:largura] - acumulado[:, a:largura - b + a]
    else:
        contagem[:, b:] = acumulado[:, b - a + 1:largura - a + 1] - acumulado[:, 1:largura - b + 1]
    return contagem


def _colunas_de_borda(claro: np.ndarray, escuro: np.ndarray, miolo_a_direita: bool
                      ) -> list[tuple[int, int, int]]:
    """Colunas que parecem borda lateral de dica: (x, início, tamanho).

    Borda de dica = pixel CLARO com o miolo PRETO logo ao lado (a maioria dos
    10 vizinhos pra dentro). Só "linha clara longa" não basta: quando a dica
    encosta no painel do inventário, a moldura dele emenda na borda da dica e
    a "linha" subia até o topo da tela (visto no jogo em 24/10/2026). Ao lado
    da grade do inventário só ~3 de 10 pixels são pretos; ao lado do miolo da
    dica, 7 a 10.

    No topo, o enfeite do banner do título deixa poucos vizinhos pretos, então
    a borda achada é ESTICADA pra cima enquanto o vão estreito logo depois dela
    continua preto (a dica tem moldura dupla, com ~4 px pretos no meio).
    """
    borda = claro & (_pretos_ao_lado(escuro, VIZINHOS, miolo_a_direita) >= VIZINHOS_PRETOS)
    borda = cv2.morphologyEx(borda.astype(np.uint8), cv2.MORPH_CLOSE, _TAPAR)
    estreita = claro & (_pretos_ao_lado(escuro, VAO, miolo_a_direita) >= VAO_PRETOS)
    estreita = cv2.morphologyEx(estreita.astype(np.uint8), cv2.MORPH_CLOSE, _TAPAR)

    colunas = []
    for x in range(borda.shape[1]):
        y0, n = _maior_sequencia(borda[:, x])
        if n >= ALTURA_MINIMA:
            while y0 > 0 and estreita[y0 - 1, x]:
                y0, n = y0 - 1, n + 1
            colunas.append((x, y0, n))
    return colunas


def achar_dica(img: np.ndarray, cursor: tuple[int, int] | None = None
               ) -> tuple[int, int, int, int] | None:
    """Devolve (x0, y0, x1, y1) da dica na imagem (BGR), ou None.

    Com `cursor` (x, y na imagem), escolhe a dica mais perto dele. Isso
    importa quando aparecem duas (a do item e a do item equipado).
    """
    mx = img.max(axis=2)
    escuro = mx < ESCURO
    # Imagem integral: soma de qualquer retângulo em tempo constante.
    preto = cv2.integral(escuro.astype(np.uint8))

    esquerdas = _colunas_de_borda(mx >= CLARO, escuro, miolo_a_direita=True)
    direitas = _colunas_de_borda(mx >= CLARO, escuro, miolo_a_direita=False)
    colunas = esquerdas + direitas

    candidatas = []
    for xe, ye, ne in esquerdas:
        for xd, yd, nd in direitas:
            if not LARGURA[0] <= xd - xe <= LARGURA[1]:
                continue
            topo, base = max(ye, yd), min(ye + ne, yd + nd)
            if base - topo < 0.85 * min(ne, nd):
                continue  # as duas bordas precisam ter quase a mesma altura
            a, b = xe + 3, xd - 3
            soma = preto[base, b] - preto[topo, b] - preto[base, a] + preto[topo, a]
            if soma / ((b - a) * (base - topo)) < MIOLO_PRETO:
                continue
            # Dentro de uma dica não existe outra borda vertical longa. Sem essa
            # regra, com duas dicas lado a lado, a borda esquerda de uma formava
            # par com a da outra. (20 px de folga: a moldura da dica é dupla.)
            if any(xe + 20 < x < xd - 20 and min(y + n, base) - max(y, topo) > (base - topo) / 2
                   for x, y, n in colunas):
                continue
            candidatas.append((xe, min(ye, yd), xd, max(ye + ne, yd + nd)))

    if not candidatas:
        return None

    def area(c):
        return (c[2] - c[0]) * (c[3] - c[1])

    if cursor is None:
        return max(candidatas, key=area)

    def distancia(c):
        cx = cursor[0]
        return max(c[0] - cx, 0, cx - c[2])  # 0 se o cursor está na faixa da dica

    perto = [c for c in candidatas if distancia(c) <= DISTANCIA_DO_CURSOR]
    if not perto:
        return None
    return min(perto, key=lambda c: (distancia(c), -area(c)))


def localizar_dica(imagem: Image.Image, cursor: tuple[int, int] | None = None
                   ) -> tuple[int, int, int, int] | None:
    """Caixa (x0, y0, x1, y1) da dica num print (PIL), já com a folga. None se não achou.

    As bordas laterais começam ABAIXO do banner do título (visto nos itens de
    set), então a caixa sobe uma folga pra não cortar o nome do item.
    """
    bgr = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)
    caixa = achar_dica(bgr, cursor)
    if caixa is None:
        return None
    x0, y0, x1, y1 = caixa
    return x0, max(0, y0 - FOLGA_TOPO), x1, min(imagem.height, y1 + FOLGA_BASE)


def recortar_dica(imagem: Image.Image, cursor: tuple[int, int] | None = None
                  ) -> Image.Image | None:
    """Recorta só a dica de um print (PIL). None se não achou dica."""
    caixa = localizar_dica(imagem, cursor)
    return imagem.crop(caixa) if caixa else None


def texto_da_dica(imagem: Image.Image, cursor: tuple[int, int] | None = None) -> str:
    """Recorta a dica e lê com OCR ampliando 2x. Sem dica, lê a imagem toda.

    Medido nos 9 prints de samples/ (afixos + nomes + armadura, 53 pontos):
      imagem inteira 48/53 · recorte justo 40/53 · recorte + folga 44/53
      recorte + folga + ampliar 2x 50/53 (todos os afixos e nomes certos).
    """
    from ocr import ler_texto  # aqui pra captura não exigir Tesseract nos testes
    return ler_texto(recortar_dica(imagem, cursor) or imagem, ampliar=AMPLIAR)


# ---------------------------------------------------------------- tela (Windows)

def _ativar_pixels_reais():
    """Sem isso, com zoom de tela (ex.: 125%), o Windows "mente" a posição do
    mouse e ela não bate com os pixels do print."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def posicao_do_cursor() -> tuple[int, int]:
    ponto = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(ponto))
    return ponto.x, ponto.y


def capturar_perto_do_cursor() -> tuple[Image.Image, tuple[int, int], tuple[int, int]]:
    """Print de uma faixa da tela em volta do mouse (altura inteira).

    Devolve a imagem, a posição do cursor DENTRO dela e onde a imagem começa
    na tela (pra converter a caixa da dica em coordenadas de tela).
    """
    _ativar_pixels_reais()
    user32 = ctypes.windll.user32
    # Tela virtual = todos os monitores juntos.
    esq, topo = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    larg, alt = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)

    cx, cy = posicao_do_cursor()
    x0 = max(esq, cx - MEIA_LARGURA_CAPTURA)
    x1 = min(esq + larg, cx + MEIA_LARGURA_CAPTURA)
    imagem = ImageGrab.grab(bbox=(x0, topo, x1, topo + alt), all_screens=True)
    return imagem, (cx - x0, cy - topo), (x0, topo)


if __name__ == "__main__":
    # Teste rápido sem o jogo: recorta a dica de um print salvo.
    #   python src/captura.py samples/lendario_demon_machine.png
    if len(sys.argv) < 2:
        print("Uso: python src/captura.py <print.png>")
        sys.exit(1)
    recorte = recortar_dica(Image.open(sys.argv[1]))
    if recorte is None:
        print("Não achei dica nesse print.")
    else:
        destino = "capturas/recorte.png"
        recorte.save(destino)
        print(f"Dica recortada ({recorte.width}x{recorte.height}) salva em {destino}")
