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

from pastas import PASTA_CAPTURAS  # capturas/ do projeto (ou do usuário, no .exe)
# Imagens guardadas em capturas/ (as mais novas). O print "sem dica" é a tela
# inteira e pode pegar outras janelas: não fica pra sempre no PC.
MAXIMO_DE_CAPTURAS = 200


def limpar_capturas(pasta: Path = PASTA_CAPTURAS, maximo: int = MAXIMO_DE_CAPTURAS) -> int:
    """Apaga as imagens mais antigas de capturas/ além das `maximo` mais novas.
    Só .png com nome de data (as do app); o histórico e o resto ficam. Devolve quantas apagou."""
    imagens = sorted(p for p in pasta.glob("[0-9]*_[0-9]*.png") if p.is_file())
    velhas = imagens[:-maximo] if maximo > 0 else imagens
    for p in velhas:
        p.unlink(missing_ok=True)
    return len(velhas)


def processo_vivo(pid: int) -> bool:
    """O processo ainda está rodando? (Windows: abre só pra esperar, sem mexer nele.)"""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    processo = kernel32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
    if not processo:
        return False  # não existe mais
    try:
        return kernel32.WaitForSingleObject(ctypes.c_void_p(processo), 0) == 0x102  # WAIT_TIMEOUT: rodando
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(processo))

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
                  builds: list[dict], salvar: bool = True,
                  salvar_sem_dica: bool = True) -> Avaliacao:
    """Print -> acha a dica -> OCR -> parser -> avaliador.

    `salvar_sem_dica=False` na avaliação automática: ela olha a tela o tempo
    todo, e um print inteiro por "alarme falso" encheria capturas/."""
    inicio = time.perf_counter()
    av = Avaliacao()
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    if salvar:
        PASTA_CAPTURAS.mkdir(exist_ok=True)

    av.caixa = localizar_dica(imagem, cursor)
    if av.caixa is None:
        av.erro = "Não achei a dica perto do mouse."
        if salvar and salvar_sem_dica:
            av.arquivo = PASTA_CAPTURAS / f"{carimbo}_sem_dica.png"
            imagem.save(av.arquivo)
            limpar_capturas()
    else:
        bgr = cv2.cvtColor(np.array(imagem.convert("RGB")), cv2.COLOR_RGB2BGR)
        av.grupo = grupo_de_dicas(bgr, av.caixa)
        recorte = imagem.crop(av.caixa)
        if salvar:
            av.arquivo = PASTA_CAPTURAS / f"{carimbo}.png"
            recorte.save(av.arquivo)
            limpar_capturas()
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
    com estilo em: "normal", "build", "ok", "falta", "motivo".
    `parcial`: não serve, mas dá pra usar enquanto upa (borda amarela)."""
    serve: bool
    titulo: str
    linhas: list[list[tuple[str, str]]]
    parcial: bool = False


def _lista(rotulo: str, afixos: list[dict], marca: str, estilo: str) -> list[tuple[str, str]]:
    linha = [(rotulo, "normal")]
    for i, a in enumerate(afixos):
        linha += [("  ", "normal")] if i else []
        linha.append((f"{a['rotulo']} {marca}", estilo))
    return linha


def _detalhe(r: dict) -> list[list[tuple[str, str]]]:
    """O que o item tem e o que falta pra build; e, se der, o que trocar no Místico."""
    tem = [a for a in r["afixos"] if a["ok"]]
    falta = [a for a in r["afixos"] if not a["ok"]]
    linhas = []
    if tem:
        linhas.append(_lista("Tem: ", tem, "✓", "ok"))
    if falta:
        linhas.append(_lista("Falta: ", falta, "✗", "falta"))
        dica = dica_do_mistico(r)
        if dica:
            linhas.append([(dica, "motivo")])
    return linhas


def dica_do_mistico(r: dict) -> str | None:
    """O Místico troca UM afixo por item: troca um que a build não usa por um que falta."""
    falta = [a["rotulo"] for a in r["afixos"] if not a["ok"]]
    if not falta or not r.get("sobrando"):
        return None
    trocaveis = [f for f in falta if f != "Encaixe"] or falta[:1]
    alvo = trocaveis[0] + (f" (ou {trocaveis[1]})" if len(trocaveis) > 1 else "")
    return f"Dica: no Místico, troque \"{r['sobrando'][0]}\" por {alvo}."


def _resumo(r: dict) -> str:
    """Uma linha curta pras outras builds (com "Todas")."""
    if not r["afixos"]:
        return r["motivo"]
    ok = sum(a["ok"] for a in r["afixos"])
    return f"{ok} de {len(r['afixos'])} afixos"


def montar_selo(av: Avaliacao) -> Selo:
    """Ex.:
        Fiendish Grips
        ✅ Unhallowed · item da build
        Tem: Destreza ✓  Vitalidade ✓  Crítico ✓
        Falta: Dano crítico ✗
        Dica: no Místico, troque "Attack Speed Increased by 5.0%" por Dano crítico.
    A build de cima ganha o detalhe; as outras (com "Todas"), uma linha cada."""
    if av.erro:
        return Selo(False, "D3 Companion", [[(av.erro, "motivo")]])
    item = av.item or {}
    titulo = item.get("nome") or f"{item.get('qualidade', '')} {item.get('tipo') or ''}".strip()
    if not av.resultados:
        return Selo(False, titulo, [[("Nenhuma build em builds/", "motivo")]])

    batem = [r for r in av.resultados if r["bate"]]
    por_enquanto = [r for r in av.resultados if r["por_enquanto"]]
    if not batem and not por_enquanto:
        r = av.resultados[0]  # a que chegou mais perto
        return Selo(False, titulo, [[("❌ Não serve", "build")],
                                    [(f"{r['apelido']}: {r['motivo']}", "motivo")]])

    if batem:
        primeira, outras, marca = batem[0], batem[1:], "✅ "
        if not primeira["afixos"]:  # gema, cubo
            o_que = primeira["motivo"]
        elif primeira["motivo"].startswith("Item da build"):
            o_que = "item da build"
        else:
            o_que = "serve neste espaço"
        if primeira["afixos"] and all(a["ok"] for a in primeira["afixos"]):
            o_que += " · tudo certo"
    else:
        # Pra upar: não é o item da build, mas serve até achar.
        primeira, outras, marca = por_enquanto[0], por_enquanto[1:], "🟡 Por enquanto · "
        o_que = primeira["motivo"]

    linhas = [[(marca, "normal"), (primeira["apelido"], "build"), (f" · {o_que}", "normal")]]
    linhas += _detalhe(primeira)
    for r in outras:
        linhas.append([(marca, "normal"), (r["apelido"], "build"), (f" · {_resumo(r)}", "normal")])
    return Selo(bool(batem), titulo, linhas, parcial=not batem)


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
