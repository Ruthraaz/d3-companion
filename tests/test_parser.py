"""
Testes do parser (Etapa 2).

Os arquivos em tests/ocr/ são a saída do OCR (Tesseract 5.4, imagem crua) para
os prints de samples/. Assim os testes rodam sem precisar do Tesseract, e os
valores esperados foram conferidos contra as imagens originais.

Rodar:
    python -m unittest discover tests
"""

import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português

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

    def test_sem_stat_changes_ignora_descricao(self):
        # Item já equipado: a dica não tem "Stat Changes", então nada separa os
        # afixos da descrição em itálico ("The cloak of one with...").
        texto = (RAIZ / "tests" / "ocr" / "lendario_cloak_garwulf.txt").read_text(encoding="utf-8")
        linhas = texto.splitlines()
        i = next(n for n, l in enumerate(linhas) if "Stat Changes" in l)
        equipado = interpretar("\n".join(linhas[:i] + linhas[i + 4:]))
        self.assertEqual(textos(equipado["secundarios"]), [
            "+156 Physical Resistance",
            "Companion - Wolf Companion now summons 3 wolves.",
        ])


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


class TestSets(unittest.TestCase):
    def test_antique_vintage_boots(self):
        boots = item("set_antique_vintage_boots")
        self.assertEqual(boots["nome"], "Antique Vintage Boots")
        self.assertEqual((boots["qualidade"], boots["tipo"], boots["slot"]), ("Set", "Boots", "Feet"))
        self.assertEqual(boots["set"]["nome"], "Gears of Dreadlands")
        self.assertEqual(boots["set"]["pecas"], [
            {"nome": "Antique Vintage Boots", "slot": "Feet"},
            {"nome": "Cold Cathode Trousers", "slot": "Legs"},
            {"nome": "Galvanized Vest", "slot": "Torso"},
            {"nome": "Dystopian Goggles", "slot": "Head"},
            {"nome": "Mechanical Pauldrons", "slot": "Shoulders"},
            {"nome": "Gas Powered Automail Forearm", "slot": "Hands"},
        ])
        # Os bônus "(2) Set: ..." não podem virar afixo do item.
        self.assertEqual(textos(boots["secundarios"]), [
            "+160 Cold Resistance",
            "Increases Gold and Health Pickup by 2 Yards.",
        ])
        self.assertEqual(len(boots["primarios"]), 4)

    def test_fiendish_grips(self):
        grips = item("set_fiendish_grips")
        self.assertEqual(grips["nome"], "Fiendish Grips")
        self.assertEqual(grips["set"]["nome"], "Unhallowed Essence")
        self.assertEqual(len(grips["set"]["pecas"]), 6)
        # OCR leu "Unsanetified"; a correção vale também pras peças.
        self.assertIn({"nome": "Unsanctified Shoulders", "slot": "Shoulders"}, grips["set"]["pecas"])
        self.assertEqual(textos(grips["primarios"]), [
            "+732 Dexterity",
            "+722 Vitality",
            "Attack Speed Increased by 5.0%",
            "Critical Hit Chance Increased by 9.0%",
        ])

    def test_litany_nome_embaralhado_vem_da_lista(self):
        anel = item("set_litany_of_the_undaunted")
        # O título saiu "LITANY)@FeTHE/UNDAUNTED"; o nome vem da lista de peças.
        self.assertEqual(anel["nome"], "Litany of the Undaunted")
        self.assertEqual(anel["set"], {"nome": "Legacy of Nightmares", "pecas": [
            {"nome": "Litany of the Undaunted", "slot": "Finger"},
            {"nome": "The Wailing Host", "slot": "Finger"},
        ]})
        self.assertEqual(anel["soquetes"], 1)
        # OCR leu "+157" como "+187": erro de leitura, não do parser.
        self.assertEqual(textos(anel["secundarios"]), [
            "+187 Cold Resistance",
            "+5695 Life after Each Kill",
        ])

    def test_cain_equipado_sem_stat_changes(self):
        luvas = item("set_cains_scrivener_equipado")
        self.assertEqual(luvas["nome"], "Cain's Scrivener")  # título veio "CAIN'S/SCRIVENER"
        self.assertEqual(luvas["armadura"], 551)
        self.assertEqual(luvas["set"]["nome"], "Cain's Destiny")
        self.assertEqual([p["nome"] for p in luvas["set"]["pecas"]],
                         ["Cain's Scrivener", "Cain's Insight", "Cain's Habit", "Cain's Travelers"])
        self.assertEqual(textos(luvas["primarios"]), [
            "+668 Dexterity",
            "+655 Vitality",
            "Critical Hit Chance Increased by 9.5%",
            "Reduces cooldown of all skills by 5.0%.",  # OCR leu "ofall"
        ])
        # Sem "Stat Changes", nem o bônus de set nem a descrição em itálico
        # ("These wrappings are covered...") podem entrar como afixo.
        self.assertEqual([a["modelo"] for a in luvas["secundarios"]], [
            "+#% Extra Gold from Monsters",  # OCR leu +39% (o certo é +33%)
            "Monster kills grant +# experience.",
        ])

    def test_item_sem_set(self):
        self.assertIsNone(item("lendario_cloak_garwulf")["set"])


class TestRaro(unittest.TestCase):
    def test_vampiric_source(self):
        anel = item("raro_vampiric_source_equipado")
        self.assertIsNone(anel["nome"])  # nome de raro é aleatório e sai embaralhado
        self.assertEqual((anel["qualidade"], anel["tipo"], anel["slot"]), ("Rare", "Ring", "Finger"))
        self.assertIsNone(anel["set"])
        self.assertEqual(textos(anel["primarios"]), [
            "+403 Dexterity",
            "+89 Resistance to All Elements",
            "Attack Speed Increased by 5.0%",
            "Chance to Deal 10% Area Damage on Hit.",
        ])
        self.assertEqual(textos(anel["secundarios"]), [
            "+3742 Life after Each Kill",  # OCR leu "Lie after Each Kil"
            "+31% Extra Gold from Monsters",
        ])
        self.assertEqual(anel["secundarios"][0]["modelo"], "+# Life after Each Kill")


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
