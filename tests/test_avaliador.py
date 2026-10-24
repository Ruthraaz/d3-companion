"""
Testes do avaliador (Etapa 3).

Duas partes:
  - itens reais (texto do OCR em tests/ocr/ -> parser -> avaliador) contra as
    builds de builds/;
  - regras isoladas com itens e builds pequenos, montados aqui.

Rodar:
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from avaliador import avaliar, avaliar_todas, carregar_builds  # noqa: E402
from builds_dos_testes import BUILDS_DOS_TESTES  # noqa: E402
from parser import estruturar_afixo, interpretar  # noqa: E402

# Só as 3 builds originais: builds importadas na pasta não podem mudar o resultado dos testes.
BUILDS = {b["nome"]: b for b in carregar_builds() if b["id"] in BUILDS_DOS_TESTES}
DREADLANDS = BUILDS["Gears of Dreadlands — Metralhar"]
UNHALLOWED = BUILDS["Unhallowed Essence — Multidisparo"]
LON = BUILDS["Legacy of Nightmares"]


def item(nome: str) -> dict:
    return interpretar((RAIZ / "tests" / "ocr" / f"{nome}.txt").read_text(encoding="utf-8"))


class TestItensReais(unittest.TestCase):
    def test_peca_do_set_certo(self):
        r = avaliar(item("set_antique_vintage_boots"), DREADLANDS)
        self.assertTrue(r["bate"])
        self.assertEqual(r["motivo"], "Item da build: Antique Vintage Boots")
        self.assertEqual(r["obrigatorios"]["ok"], ["Destreza"])  # o rótulo da build
        self.assertEqual(r["nota"], 1.0)

    def test_afixos_na_ordem_da_build_pro_selo(self):
        r = avaliar(item("set_fiendish_grips"), UNHALLOWED)
        self.assertEqual(r["apelido"], "Unhallowed")
        self.assertEqual(r["afixos"], [
            {"rotulo": "Destreza", "ok": True},
            {"rotulo": "Vitalidade", "ok": True},
            {"rotulo": "Crítico", "ok": True},
            {"rotulo": "Dano crítico", "ok": False},
        ])

    def test_peca_de_outro_set(self):
        r = avaliar(item("set_antique_vintage_boots"), UNHALLOWED)
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "A build pede: Hell Walkers")

    def test_luvas_unhallowed_nota_parcial(self):
        r = avaliar(item("set_fiendish_grips"), UNHALLOWED)
        self.assertTrue(r["bate"])
        self.assertEqual(r["desejaveis"]["ok"], ["Vitalidade", "Crítico"])
        self.assertEqual(r["desejaveis"]["faltando"], ["Dano crítico"])
        self.assertEqual(r["nota"], 0.67)

    def test_lon_exige_ancient(self):
        r = avaliar(item("set_antique_vintage_boots"), LON)
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "Precisa ser Ancient")

    def test_lon_aneis_do_set_nao_precisam_ser_ancient(self):
        r = avaliar(item("set_litany_of_the_undaunted"), LON)
        self.assertTrue(r["bate"])
        self.assertEqual(r["desejaveis"]["ok"], ["Encaixe"])

    def test_arma_qualquer_com_afixos(self):
        # "2-Hand" do parser cai no espaço "Weapon" da build.
        r = avaliar(item("lendario_demon_machine"), DREADLANDS)
        self.assertTrue(r["bate"])
        self.assertIn("Dano da arma", r["desejaveis"]["ok"])  # "+#-# * Damage" pegou "Fire Damage"

    def test_raro_serve_mas_com_nota_baixa(self):
        r = avaliar(item("raro_vampiric_source_equipado"), DREADLANDS)
        self.assertTrue(r["bate"])
        self.assertEqual(r["nota"], 0.0)

    def test_gemas(self):
        self.assertTrue(avaliar(item("gema_zei"), DREADLANDS)["bate"])
        r = avaliar(item("gema_pain_enhancer"), DREADLANDS)
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "Gema fora da build")

    def test_ordem_das_builds(self):
        resultados = avaliar_todas(item("set_fiendish_grips"), list(BUILDS.values()))
        self.assertEqual(resultados[0]["build"], "Unhallowed Essence — Multidisparo")
        self.assertEqual([r["bate"] for r in resultados], [True, False, False])


def item_falso(*afixos: str, **campos) -> dict:
    return {"nome": "Teste", "qualidade": "Legendary", "tipo": "Ring", "slot": "Finger",
            "classe": None, "soquetes": 0, "secundarios": [],
            "primarios": [estruturar_afixo(a) for a in afixos]} | campos


def build_falsa(**espaco) -> dict:
    return {"nome": "Teste", "classe": "Demon Hunter", "espacos": {"Finger": espaco}}


class TestRegras(unittest.TestCase):
    def test_coringa(self):
        build = build_falsa(obrigatorios=["+# * Resistance"])
        self.assertTrue(avaliar(item_falso("+160 Cold Resistance"), build)["bate"])
        self.assertTrue(avaliar(item_falso("+90 Fire Resistance"), build)["bate"])
        self.assertFalse(avaliar(item_falso("+89 Resistance to All Elements"), build)["bate"])

    def test_minimo(self):
        build = build_falsa(obrigatorios=[{"modelo": "+# Dexterity", "minimo": 400}])
        self.assertTrue(avaliar(item_falso("+458 Dexterity"), build)["bate"])
        r = avaliar(item_falso("+380 Dexterity"), build)
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "Falta: +# Dexterity (mín. 400)")

    def test_sem_rotulo_usa_o_modelo(self):
        r = avaliar(item_falso("+458 Dexterity"), build_falsa(desejaveis=["+# Dexterity"]))
        self.assertEqual(r["afixos"], [{"rotulo": "+# Dexterity", "ok": True}])
        self.assertEqual(r["apelido"], "Teste")  # sem apelido, usa o nome

    def test_soquete(self):
        build = build_falsa(obrigatorios=["@soquete"])
        self.assertFalse(avaliar(item_falso(), build)["bate"])
        self.assertTrue(avaliar(item_falso(soquetes=1), build)["bate"])

    def test_ignora_maiusculas_e_ponto_final(self):
        build = build_falsa(obrigatorios=["reduces cooldown of all skills by #%"])
        self.assertTrue(avaliar(item_falso("Reduces cooldown of all skills by 5.0%."), build)["bate"])

    def test_outra_classe(self):
        r = avaliar(item_falso("+458 Dexterity", classe="Wizard"), build_falsa())
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "Item de Wizard")

    def test_espaco_fora_da_build_aceita_qualquer_item(self):
        r = avaliar(item_falso(slot="Waist"), build_falsa(itens=["Algo"]))
        self.assertTrue(r["bate"])


if __name__ == "__main__":
    unittest.main()
