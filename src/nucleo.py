"""
Núcleo do app: do print ao veredito, sem nenhuma interface.

O overlay (Etapa 5) e a futura janela principal usam só isto. Aqui não entra
Qt nem HTML: tudo é dado simples (dataclass, dict, texto), e por isso dá pra
testar sem abrir janela.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from avaliador import avaliar_todas
from captura import AMPLIAR, FOLGA_TOPO, grupo_de_dicas, localizar_dica
from ocr import ler_texto
from parser import interpretar

PASTA_CAPTURAS = Path(__file__).resolve().parent.parent / "capturas"

Caixa = tuple[int, int, int, int]  # (x0, y0, x1, y1)


@dataclass
class Avaliacao:
    item: dict | None = None
    resultados: list[dict] = field(default_factory=list)
    caixa: Caixa | None = None      # onde a dica está, em coordenadas da imagem
    grupo: tuple[int, int] | None = None  # (x0, x1) da dica + dicas coladas (Equipped)
    erro: str | None = None
    arquivo: Path | None = None     # recorte (ou print, se não achou dica) salvo
    segundos: float = 0.0


def avaliar_print(imagem: Image.Image, cursor: tuple[int, int] | None,
                  builds: list[dict], salvar: bool = True) -> Avaliacao:
    """Print -> acha a dica -> OCR -> parser -> avaliador."""
    inicio = time.perf_counter()
    av = Avaliacao()
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    if salvar:
        PASTA_CAPTURAS.mkdir(exist_ok=True)

    av.caixa = localizar_dica(imagem, cursor)
    if av.caixa is None:
        av.erro = "Não achei a dica perto do mouse."
        if salvar:
            av.arquivo = PASTA_CAPTURAS / f"{carimbo}_sem_dica.png"
            imagem.save(av.arquivo)
    else:
        bgr = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)
        av.grupo = grupo_de_dicas(bgr, av.caixa)
        recorte = imagem.crop(av.caixa)
        if salvar:
            av.arquivo = PASTA_CAPTURAS / f"{carimbo}.png"
            recorte.save(av.arquivo)
        try:
            av.item = interpretar(ler_texto(recorte, ampliar=AMPLIAR))
            av.resultados = avaliar_todas(av.item, builds)
        except ValueError:
            av.erro = "Li a dica, mas não entendi o item."

    av.segundos = time.perf_counter() - inicio
    return av


# ---------------------------------------------------------------- selo

@dataclass
class Selo:
    """O que o overlay mostra. Cada linha é uma lista de pedaços (texto, estilo),
    com estilo em: "normal", "build", "ok", "falta", "motivo"."""
    serve: bool
    titulo: str
    linhas: list[list[tuple[str, str]]]


def montar_selo(av: Avaliacao) -> Selo:
    """Ex.: ✅ Dreadlands · Destreza ✓ Crítico ✓ Encaixe ✗"""
    if av.erro:
        return Selo(False, "D3 Companion", [[(av.erro, "motivo")]])
    item = av.item or {}
    titulo = item.get("nome") or f"{item.get('qualidade', '')} {item.get('tipo') or ''}".strip()
    if not av.resultados:
        return Selo(False, titulo, [[("Nenhuma build em builds/", "motivo")]])

    batem = [r for r in av.resultados if r["bate"]]
    if not batem:
        r = av.resultados[0]  # a que chegou mais perto
        return Selo(False, titulo, [[("❌ Não serve", "build")],
                                    [(f"{r['apelido']}: {r['motivo']}", "motivo")]])

    linhas = []
    for r in batem:
        linha = [("✅ ", "normal"), (r["apelido"], "build")]
        if r["afixos"]:
            linha.append((" · ", "normal"))
            for i, a in enumerate(r["afixos"]):
                if i:
                    linha.append(("  ", "normal"))
                linha.append((f"{a['rotulo']} {'✓' if a['ok'] else '✗'}", "ok" if a["ok"] else "falta"))
        else:
            linha.append((f" · {r['motivo']}", "normal"))
        linhas.append(linha)
    return Selo(True, titulo, linhas)


def texto_do_selo(selo: Selo) -> str:
    """O selo em texto puro (terminal e testes)."""
    return "\n".join([selo.titulo] + ["".join(t for t, _ in linha) for linha in selo.linhas])


def caixa_na_tela(av: Avaliacao, origem: tuple[int, int], cursor: tuple[int, int]) -> Caixa:
    """Onde a dica está na TELA, pra posicionar o selo ao lado dela.

    `origem` é onde o print começa na tela; `cursor` é a posição do mouse no
    print. A caixa do recorte sobe FOLGA_TOPO pra pegar o título; aqui
    descontamos, pra o selo alinhar com o topo da dica. Sem dica, usa o mouse.
    """
    ox, oy = origem
    if av.caixa is None:
        mx, my = cursor[0] + ox, cursor[1] + oy
        return mx, my, mx + 1, my + 1
    x0, y0, x1, y1 = av.caixa
    if av.grupo:  # o selo vai pro lado de fora da dica do item equipado
        x0, x1 = av.grupo
    return x0 + ox, y0 + FOLGA_TOPO + oy, x1 + ox, y1 + oy


def posicao_do_selo(caixa: Caixa, tamanho: tuple[int, int], tela: Caixa,
                    distancia: int = 8) -> tuple[int, int]:
    """Onde pôr o selo (canto superior esquerdo), em coordenadas de tela.

    Fica à direita da dica, alinhado com o topo dela; se não couber, à esquerda.
    Nunca sai da tela.
    """
    x0, y0, x1, _ = caixa
    largura, altura = tamanho
    tx0, ty0, tx1, ty1 = tela
    x = x1 + distancia if x1 + distancia + largura <= tx1 else x0 - distancia - largura
    x = min(max(x, tx0), tx1 - largura)
    y = min(max(y0, ty0), ty1 - altura)
    return x, y
