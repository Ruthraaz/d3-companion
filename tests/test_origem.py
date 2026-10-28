"""
Testes do "Como conseguir" (src/origem.py) e dos rótulos no idioma do app,
sem internet: os detalhes do item são montados aqui, no formato da API da Blizzard.

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

import json  # noqa: E402

from avaliador import _rotulo  # noqa: E402
from blizzard import ErroBlizzard, NaoEncontrado  # noqa: E402
from origem import ITENS_DO_CACHE, origem, origens_dos_itens  # noqa: E402


def textos(origens):
    return [o["texto"] for o in origens]


class TestOrigem(unittest.TestCase):
    def test_item_do_cache_nem_precisa_da_blizzard(self):
        o = origem("Ring of Royal Grandeur", None)
        self.assertEqual(o[0]["vars"], {"ato": "I"})
        self.assertIn("Não cai de monstros nem sai na Kadala ou no cubo.", textos(o))
        self.assertEqual(origem("pride's fall", None)[0]["vars"], {"ato": "III"})  # sem ligar pra maiúsculas

    def test_cache_tem_21_itens_e_nada_no_ato_iv(self):
        self.assertEqual(sum(map(len, ITENS_DO_CACHE.values())), 21)
        self.assertNotIn("IV", ITENS_DO_CACHE)

    def test_forjado(self):
        self.assertEqual(textos(origem("Hellfire Amulet", {"tooltipParams": "/artisan/jeweler/recipe/x"})),
                         ["Feito pelo Joalheiro (precisa do plano)."])
        self.assertEqual(textos(origem("Cain's Habit", {"tooltipParams": "/artisan/blacksmith/recipe/x"})),
                         ["Forjado pelo Ferreiro (precisa do plano)."])

    def test_gema_lendaria(self):
        self.assertEqual(textos(origem("Zei's Stone of Vengeance", {"typeName": "Legendary Gem"})),
                         ["Cai dos Guardiões da Grande Fenda."])

    def test_lendario_comum_e_temporada(self):
        comum = textos(origem("Fiendish Grips", {"tooltipParams": "/item/fiendish-grips", "isSeasonRequiredToDrop": False}))
        self.assertIn("Aposta na Kadala, com Fragmentos de Sangue.", comum)
        self.assertNotIn("Só cai com personagem de temporada.", comum)
        self.assertIn("Só cai com personagem de temporada.",
                      textos(origem("X", {"tooltipParams": "/item/x", "isSeasonRequiredToDrop": True})))

    def test_sem_detalhes_nao_inventa(self):
        self.assertEqual(origem("Fiendish Grips", None), [])

    def test_varios_itens_sem_internet(self):
        class SemRede:
            def detalhes_do_item(self, nome):
                if nome == "Desconhecido":
                    raise NaoEncontrado("não conhece")
                raise ErroBlizzard("sem internet")
        o = origens_dos_itens(["Fiendish Grips", "Desconhecido", "Avarice Band", "Fiendish Grips"], SemRede())
        self.assertEqual(o["Fiendish Grips"], [])
        self.assertEqual(o["Desconhecido"], [])
        self.assertEqual(o["Avarice Band"][0]["vars"], {"ato": "III"})

    def test_frases_traduzidas(self):
        en = json.loads((RAIZ / "src" / "web" / "dados" / "en.json").read_text(encoding="utf-8"))
        frases = {o["texto"] for nome in ("Avarice Band",) for o in origem(nome, None)}
        for detalhes in ({"tooltipParams": "/artisan/blacksmith/r"}, {"tooltipParams": "/artisan/jeweler/r"},
                         {"tooltipParams": "/artisan/mystic/r"}, {"tooltipParams": "/artisan/novo/r"},
                         {"typeName": "Legendary Gem"}, {"tooltipParams": "/item/x", "isSeasonRequiredToDrop": True}):
            frases |= set(textos(origem("X", detalhes)))
        self.assertEqual([f for f in frases | {"Como conseguir"} if f not in en], [])


class TestRotuloNoIdioma(unittest.TestCase):
    def tearDown(self):
        os.environ["D3C_IDIOMA"] = "pt"

    def test_em_portugues_fica_como_esta(self):
        self.assertEqual(_rotulo({"modelo": "Increases Multishot Damage by #% *", "rotulo": "Dano de Tiro Múltiplo"}),
                         "Dano de Tiro Múltiplo")
        self.assertEqual(_rotulo({"modelo": "+# Dexterity", "rotulo": "Destreza", "minimo": 500}), "Destreza (mín. 500)")

    def test_em_ingles_nada_de_portugues(self):
        os.environ["D3C_IDIOMA"] = "en"
        self.assertEqual(_rotulo({"modelo": "Increases Multishot Damage by #% *", "rotulo": "Dano de Tiro Múltiplo"}),
                         "Multishot damage")
        self.assertEqual(_rotulo({"modelo": "+#-# x", "rotulo": "Dano mín–máx"}), "Min–max damage")
        self.assertEqual(_rotulo({"modelo": "+# x", "rotulo": "Dano da arma"}), "Weapon damage")
        self.assertEqual(_rotulo({"modelo": "+# Dexterity", "rotulo": "Destreza", "minimo": 500}), "Dexterity (min. 500)")
        self.assertEqual(_rotulo({"modelo": "@soquete", "rotulo": "Encaixe"}), "Socket")


if __name__ == "__main__":
    unittest.main()
