"""
Testes do parser (Etapa 2).

Os arquivos em tests/ocr/ são a saída do OCR (Tesseract 5.4, imagem crua) para
os prints de samples/. Assim os testes rodam sem precisar do Tesseract, e os
valores esperados foram conferidos contra as imagens originais.

Rodar:
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from parser import interpretar, limpar_linha  # noqa: E402


def item(nome: str) -> dict:
    return interpretar((RAIZ / "tests" / "ocr" / f"{nome}.txt").read_text(encoding="utf-8"))


def textos(afixos: list[dict]) -> list[str]:
    return [a["texto"] for a in afixos]


class TestCloakGarwulf(unittest.TestCase):
    def setUp(self):
        self.item = item("lendario_cloak_garwulf")

    def test_cabecalho(self):
        self.assertEqual(self.item["nome"], "The Cloak of the Garwulf")  # "@" -> "O"
        self.assertEqual(self.item["qualidade"], "Legendary")
        self.assertEqual(self.item["tipo"], "Cloak")
        self.assertEqual(self.item["slot"], "Torso")
        self.assertEqual(self.item["classe"], "Demon Hunter")
        self.assertEqual(self.item["armadura"], 670)
        self.assertIsNone(self.item["dps"])

    def test_primarios(self):
        self.assertEqual(textos(self.item["primarios"]), [
            "+458 Dexterity",
            "+14% Life",  # OCR leu "Lite"
            "Increases Sentry Damage by 13% (Demon Hunter Only)",  # vinha em 2 linhas
        ])
        self.assertEqual(self.item["primarios"][0]["modelo"], "+# Dexterity")
        self.assertEqual(self.item["primarios"][0]["valores"], [458])

    def test_secundarios_e_soquetes(self):
        self.assertEqual(textos(self.item["secundarios"]), [
            "+156 Physical Resistance",
            "Companion - Wolf Companion now summons 3 wolves.",
        ])
        self.assertEqual(self.item["soquetes"], 3)
        self.assertEqual(self.item["nivel_requerido"], 1)

    def test_ignora_stat_changes(self):
        todos = " ".join(textos(self.item["primarios"] + self.item["secundarios"]))
        self.assertNotIn("Toughness", todos)
        self.assertNotIn("Recovery", todos)


class TestDemonMachine(unittest.TestCase):
    def setUp(self):
        self.item = item("lendario_demon_machine")

    def test_cabecalho(self):
        self.assertEqual(self.item["nome"], "Demon Machine")
        self.assertEqual(self.item["tipo"], "Crossbow")
        self.assertEqual(self.item["slot"], "2-Hand")
        self.assertEqual(self.item["dps"], 2174.2)  # e não 244,377 da tela de personagem
        self.assertEqual(self.item["dano"], [1794, 2159])
        self.assertEqual(self.item["ataques_por_segundo"], 1.1)

    def test_primarios(self):
        self.assertEqual(textos(self.item["primarios"]), [
            "+1015-1214 Fire Damage",
            "+743 Dexterity",
            "+741 Vitality",
            "Chance to Deal 23% Area Damage on Hit.",
        ])
        self.assertEqual(self.item["primarios"][0]["modelo"], "+#-# Fire Damage")
        self.assertEqual(self.item["primarios"][0]["valores"], [1015, 1214])

    def test_secundarios(self):  # título da seção veio como "°S\ Secondary"
        self.assertEqual(textos(self.item["secundarios"]), [
            "+10 Maximum Discipline (Demon Hunter Only)",
            "54% chance to shoot explosive bolts when attacking.",
        ])
        self.assertEqual(self.item["soquetes"], 0)


class TestGemas(unittest.TestCase):
    def test_zei(self):
        gema = item("gema_zei")
        self.assertEqual(gema["nome"], "Zei's Stone of Vengeance")
        self.assertEqual(gema["tipo"], "Gem")
        self.assertEqual(gema["rank"], 0)
        self.assertEqual(textos(gema["efeitos"]), [
            "Damage you deal is increased by 4.00% for every 10 yards between you"
            " and the enemy hit. Maximum 20.00% increase at 50 yards.",
            "20% chance on hit to Stun the enemy for 1 second.",
        ])
        self.assertNotIn("requer_rank", gema["efeitos"][0])
        self.assertEqual(gema["efeitos"][1]["requer_rank"], 25)

    def test_pain_enhancer(self):
        gema = item("gema_pain_enhancer")
        self.assertEqual(gema["nome"], "Pain Enhancer")
        self.assertEqual(textos(gema["efeitos"]), [
            "Critical hits cause the enemy to bleed for 2,500.0% weapon damage"
            " as Physical over 3 seconds.",
            "Gain Blood Frenzy, granting you 3% increased Attack Speed for each"
            " bleeding enemy within 20 yards.",
        ])
        self.assertEqual(gema["efeitos"][0]["valores"], [2500.0, 3])
        self.assertEqual(gema["efeitos"][1]["requer_rank"], 25)


class TestLimparLinha(unittest.TestCase):
    def test_lixo_nas_bordas(self):
        self.assertEqual(limpar_linha("ies +741 Vitality i="), "+741 Vitality")
        self.assertEqual(limpar_linha("+1015-1214 Fire Damage iA"), "+1015-1214 Fire Damage")
        self.assertEqual(limpar_linha("“| @ Chance to Deal 23% Area Damage on Hit. sai,"),
                         "Chance to Deal 23% Area Damage on Hit.")
        self.assertEqual(limpar_linha("‘© Companion - Wolf Companion now summons 3 wolves."),
                         "Companion - Wolf Companion now summons 3 wolves.")


if __name__ == "__main__":
    unittest.main()
