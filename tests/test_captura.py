"""
Testes da captura (Etapa 4): achar e recortar a dica dentro de um print.

  - TestAcharDica: detecção do retângulo da dica nos prints de samples/
    (só OpenCV, não precisa do Tesseract).
  - TestCaminhoCompleto: o texto em tests/ocr_recorte/ é a saída real do app
    (recorte + OCR ampliado 2x). Comparamos o parser com o GABARITO, conferido
    olhando as imagens — aqui não vale "o que o OCR leu", tem que estar CERTO.

Rodar:
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from captura import achar_dica  # noqa: E402
from parser import interpretar  # noqa: E402


def amostra(nome: str) -> np.ndarray:
    return cv2.imread(str(RAIZ / "samples" / f"{nome}.png"))


class TestAcharDica(unittest.TestCase):
    def test_acha_em_todos_os_prints(self):
        for p in sorted((RAIZ / "samples").glob("*.png")):
            with self.subTest(p.name):
                self.assertIsNotNone(achar_dica(cv2.imread(str(p))))

    def test_deixa_a_tela_de_personagem_de_fora(self):
        # No Demon Machine a tela de personagem fica à direita (x > 455).
        x0, y0, x1, y1 = achar_dica(amostra("lendario_demon_machine"))
        self.assertAlmostEqual(x0, 38, delta=4)
        self.assertAlmostEqual(y0, 208, delta=4)
        self.assertAlmostEqual(x1, 453, delta=4)
        self.assertAlmostEqual(y1, 890, delta=4)

    def test_dica_encostada_no_inventario(self):
        # Print real do jogo: a dica do Zei começa logo abaixo do painel do
        # inventário. A moldura do painel emendava na borda e a caixa subia
        # até o topo da tela (ou nem era achada).
        img = amostra("jogo_zei_abaixo_do_inventario")
        x0, y0, x1, y1 = achar_dica(img, cursor=(600, 700))
        self.assertAlmostEqual(x0, 651, delta=4)
        self.assertAlmostEqual(x1, 1066, delta=4)
        self.assertGreater(y0, 620)  # o inventário acaba em y≈628
        self.assertAlmostEqual(y1, 1063, delta=6)

    def test_duas_dicas_escolhe_a_mais_perto_do_cursor(self):
        zei, pain = amostra("gema_zei"), amostra("gema_pain_enhancer")
        altura = max(zei.shape[0], pain.shape[0])
        def ajustar(img):
            return cv2.copyMakeBorder(img, 0, altura - img.shape[0], 0, 0, cv2.BORDER_CONSTANT)
        tela = np.hstack([ajustar(zei), ajustar(pain)])  # Zei à esquerda, Pain à direita
        largura_zei = zei.shape[1]

        esquerda = achar_dica(tela, cursor=(80, 300))
        direita = achar_dica(tela, cursor=(largura_zei + 520, 300))
        self.assertLess(esquerda[2], largura_zei)
        self.assertGreater(direita[0], largura_zei)

    def test_sem_dica(self):
        self.assertIsNone(achar_dica(np.full((600, 800, 3), 40, np.uint8)))  # fundo cinza
        self.assertIsNone(achar_dica(np.zeros((600, 800, 3), np.uint8)))      # tudo preto

    def test_dica_longe_do_cursor_e_ignorada(self):
        img = amostra("gema_zei")  # dica entre x=91 e x=506
        self.assertIsNone(achar_dica(img, cursor=(img.shape[1] + 400, 300)))


# Gabarito: (nome, armadura, afixos) conferido nas imagens originais.
GABARITO = {
    "lendario_cloak_garwulf": ("The Cloak of the Garwulf", 670, [
        "+458 Dexterity", "+14% Life", "Increases Sentry Damage by 13% (Demon Hunter Only)",
        "+156 Physical Resistance", "Companion - Wolf Companion now summons 3 wolves."]),
    "lendario_demon_machine": ("Demon Machine", None, [
        "+1015-1214 Fire Damage", "+743 Dexterity", "+741 Vitality",
        "Chance to Deal 23% Area Damage on Hit.", "+10 Maximum Discipline (Demon Hunter Only)",
        "54% chance to shoot explosive bolts when attacking."]),
    "raro_vampiric_source_equipado": (None, None, [
        "+403 Dexterity", "+89 Resistance to All Elements", "Attack Speed Increased by 5.0%",
        "Chance to Deal 10% Area Damage on Hit.", "+3742 Life after Each Kill",
        "+31% Extra Gold from Monsters"]),
    "set_antique_vintage_boots": ("Antique Vintage Boots", 551, [
        "+458 Dexterity", "+478 Vitality", "+12% Movement Speed",
        "Increases Impale Damage by 13% (Demon Hunter Only)", "+160 Cold Resistance",
        "Increases Gold and Health Pickup by 2 Yards."]),
    "set_cains_scrivener_equipado": ("Cain's Scrivener", None, [  # armadura: OCR não lê
        "+668 Dexterity", "+655 Vitality", "Critical Hit Chance Increased by 9.5%",
        "Reduces cooldown of all skills by 5.0%.", "+33% Extra Gold from Monsters",
        "Monster kills grant +192 experience."]),
    "set_fiendish_grips": ("Fiendish Grips", 581, [
        "+732 Dexterity", "+722 Vitality", "Attack Speed Increased by 5.0%",
        "Critical Hit Chance Increased by 9.0%", "+160 Cold Resistance",
        "Monster kills grant +165 experience."]),
    "set_litany_of_the_undaunted": ("Litany of the Undaunted", None, [
        "+427 Dexterity", "+13% Life", "Reduces all resource costs by 6.0%.",
        "+157 Cold Resistance", "+5695 Life after Each Kill"]),
    "gema_zei": ("Zei's Stone of Vengeance", None, []),
    "gema_pain_enhancer": ("Pain Enhancer", None, []),
    "jogo_zei_abaixo_do_inventario": ("Zei's Stone of Vengeance", None, []),
}


class TestCaminhoCompleto(unittest.TestCase):
    def test_gabarito(self):
        for nome, (nome_item, armadura, afixos) in GABARITO.items():
            with self.subTest(nome):
                texto = (RAIZ / "tests" / "ocr_recorte" / f"{nome}.txt").read_text(encoding="utf-8")
                item = interpretar(texto)
                self.assertEqual(item["nome"], nome_item)
                lidos = [a["texto"] for a in item.get("primarios", []) + item.get("secundarios", [])]
                self.assertEqual(lidos, afixos)
                if armadura:
                    self.assertEqual(item["armadura"], armadura)

    def test_armadura_nunca_errada(self):
        # Quando a armadura não é lida, tem que vir None, nunca um número errado.
        for nome, (_, armadura, _) in GABARITO.items():
            with self.subTest(nome):
                texto = (RAIZ / "tests" / "ocr_recorte" / f"{nome}.txt").read_text(encoding="utf-8")
                lida = interpretar(texto).get("armadura")
                self.assertIn(lida, (armadura, None))


if __name__ == "__main__":
    unittest.main()
