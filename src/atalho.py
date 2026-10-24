"""
Atalho global do teclado, configurável no .env (ATALHO=F8, Ctrl+F8, Alt+Q...).

Usa o RegisterHotKey do próprio Windows: o sistema avisa o app quando a tecla
é apertada, mesmo com o jogo em foco. Nada de ler memória ou se injetar no jogo.

Só um programa por vez pode registrar a mesma tecla. Se outro já pegou (ex.:
o Battle.net usa o F12), o app avisa e sugere teclas livres.
"""

import ctypes

MOD_NOREPEAT = 0x4000  # segurar a tecla não dispara várias vezes
MODIFICADORES = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}

# Códigos "VK_" do Windows.
TECLAS = (
    {f"f{i}": 0x6F + i for i in range(1, 25)}
    | {chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)}
    | {str(d): 0x30 + d for d in range(10)}
    | {"insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
       "pageup": 0x21, "pagedown": 0x22, "pause": 0x13}
)

SUGESTOES = ["F8", "F7", "F9", "F10", "Ctrl+F8", "Alt+F8", "Shift+F8", "Insert", "Pause"]


def ler_atalho(texto: str) -> tuple[int, int]:
    """"Ctrl+F8" -> (modificadores, código da tecla). Erro se não reconhecer."""
    partes = [p.strip().lower() for p in texto.split("+") if p.strip()]
    if not partes:
        raise ValueError("atalho vazio")
    *mods, tecla = partes
    if tecla not in TECLAS:
        raise ValueError(f"tecla desconhecida: {tecla!r}")
    valor = 0
    for m in mods:
        if m not in MODIFICADORES:
            raise ValueError(f"modificador desconhecido: {m!r} (use Ctrl, Alt, Shift ou Win)")
        valor |= MODIFICADORES[m]
    return valor, TECLAS[tecla]


def registrar(texto: str, ident: int = 1) -> bool:
    """Registra o atalho pra thread atual. False se outro programa já usa."""
    mods, vk = ler_atalho(texto)
    return bool(ctypes.windll.user32.RegisterHotKey(None, ident, mods | MOD_NOREPEAT, vk))


def esta_livre(texto: str) -> bool:
    if registrar(texto, ident=0xBEEF):
        ctypes.windll.user32.UnregisterHotKey(None, 0xBEEF)
        return True
    return False


def sugestoes_livres(evitar: str = "") -> list[str]:
    return [s for s in SUGESTOES if s.lower() != evitar.lower() and esta_livre(s)]
