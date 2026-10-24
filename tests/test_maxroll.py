"""
Testes do leitor de builds do Maxroll (src/maxroll.py).

Não usam internet: o planner e o data.json são pequenos, no mesmo formato
que o Maxroll devolve (conferido com o planner 345357607, UE Multishot).

Rodar:
    python -m unittest discover tests
"""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from avaliador import problemas_da_build  # noqa: E402
from maxroll import (ErroMaxroll, baixar_planner, classe_do_planner, converter,  # noqa: E402
                     dados_do_planejador, e_de_seguidor, link_de_guia, planners_do_link, salvar_build,
                     id_do_link, nome_do_arquivo, nomes_dos_perfis)

DADOS = {
    "items": {
        "Unique_Helm_Set_03_p2": {"name": "Accursed Visage", "ids": []},
        "Unique_Ring_Set_001_x1": {"name": "Focus", "ids": []},
        "Unique_Ring_Set_002_x1": {"name": "Restraint", "ids": []},
        "P61_Unique_Bow_104_x1": {"name": "Yang's Recurve", "ids": []},
        "P69_Unique_Bow_102": {"name": "Odyssey's End", "ids": []},
        "P3_Unique_Ring_107": {"name": "Ring of Royal Grandeur", "ids": ["Unique_Ring_107_x1"]},
    },
    "legendaryGems": {"zei": {"name": "Zei's Stone of Vengeance"}, "trapped": {"name": "Bane of the Trapped"}},
}

PERFIL = {
    "name": "Solo Push", "class": "demonhunter",
    "skills": [["entanglingshot", "b"], ["multishot", "a"]],
    "passives": ["culltheweak", "ambush"],
    "kanai": {"weapon": "P69_Unique_Bow_102", "jewelry": "Unique_Ring_107_x1"},
    "items": {
        "head": {"id": "Unique_Helm_Set_03_p2", "gems": [[9, "topaz"]]},
        "leftfinger": {"id": "Unique_Ring_Set_001_x1", "gems": [["trapped", 150]]},
        "rightfinger": {"id": "Unique_Ring_Set_002_x1", "gems": [["zei", 150]]},
        "mainhand": {"id": "P61_Unique_Bow_104_x1"},
        "waist": {"id": "Item_Que_Nao_Existe"},
    },
}
PLANNER = {"_nome": "Sanc UE Multishot", "_numero": 345357607, "activeProfile": 0, "class": "demonhunter",
           "profiles": [PERFIL, {"name": "Speed", "class": "demonhunter", "items": {}}]}

HABILIDADES = {
    "ativas": [{"slug": "entangling-shot"}, {"slug": "multishot"}],
    "passivas": [{"slug": "cull-the-weak"}, {"slug": "ambush"}],
}


class TestLink(unittest.TestCase):
    def test_aceita_link_e_numero(self):
        self.assertEqual(id_do_link("https://maxroll.gg/d3/planner/345357607"), 345357607)
        self.assertEqual(id_do_link("maxroll.gg/d3/planner/345357607#2"), 345357607)
        self.assertEqual(id_do_link(" 345357607 "), 345357607)

    def test_link_sem_numero_explica(self):
        with self.assertRaisesRegex(ErroMaxroll, "guia de D3 do Maxroll"):
            id_do_link("https://www.google.com")

    def test_link_de_guia(self):
        self.assertEqual(link_de_guia("maxroll.gg/d3/guides/shadow-impale-demon-hunter-guide#skills"),
                         "https://maxroll.gg/d3/guides/shadow-impale-demon-hunter-guide")
        self.assertIsNone(link_de_guia("https://maxroll.gg/d4/guides/algum-guide"))  # D4 não

    def test_guia_traz_as_builds_da_pagina_sem_repetir(self):
        html = ('<div data-d3planner-id="236100095"></div><p>texto</p>'
                '<div data-d3planner-id="112481789"></div><div data-d3planner-id="236100095"></div>')
        abrir = lambda pedido, timeout=None: io.BytesIO(html.encode())  # noqa: E731
        self.assertEqual(planners_do_link("https://maxroll.gg/d3/guides/x-guide", abrir), [236100095, 112481789])

    def test_guia_sem_builds(self):
        abrir = lambda pedido, timeout=None: io.BytesIO(b"<html>nada</html>")  # noqa: E731
        with self.assertRaisesRegex(ErroMaxroll, "Não achei nenhuma build"):
            planners_do_link("https://maxroll.gg/d3/guides/x-guide", abrir)

    def test_link_de_planner_nao_abre_pagina(self):
        def nao_abre(pedido, timeout=None):
            raise AssertionError("não devia abrir a página")
        self.assertEqual(planners_do_link("https://maxroll.gg/d3/planner/345357607", nao_abre), [345357607])


class TestConverter(unittest.TestCase):
    def setUp(self):
        self.build = converter(PLANNER, DADOS, HABILIDADES)

    def test_itens_por_espaco_com_os_dois_aneis(self):
        e = self.build["espacos"]
        self.assertEqual(e["Head"]["itens"], ["Accursed Visage"])
        self.assertEqual(e["Finger"]["itens"], ["Focus", "Restraint"])
        self.assertEqual(e["Weapon"]["itens"], ["Yang's Recurve"])

    def test_item_desconhecido_fica_avisado_e_fora(self):
        self.assertNotIn("Waist", self.build["espacos"])
        self.assertEqual(self.build["_itens_nao_reconhecidos"], ["Item_Que_Nao_Existe"])

    def test_gemas_lendarias_e_nao_as_comuns(self):
        self.assertEqual(self.build["gemas"], ["Bane of the Trapped", "Zei's Stone of Vengeance"])

    def test_cubo_aceita_codigo_alternativo(self):
        self.assertEqual(self.build["cubo"], {"arma": "Odyssey's End", "joia": "Ring of Royal Grandeur"})

    def test_habilidades_com_codigo_da_blizzard(self):
        self.assertEqual(self.build["habilidades"], {
            "ativas": [{"habilidade": "entangling-shot", "runa": "b"}, {"habilidade": "multishot", "runa": "a"}],
            "passivas": ["cull-the-weak", "ambush"],
        })

    def test_sem_blizzard_fica_o_codigo_do_maxroll(self):
        build = converter(PLANNER, DADOS)
        self.assertEqual(build["habilidades"]["ativas"][0]["habilidade"], "entanglingshot")

    def test_classe_atributo_e_fonte(self):
        self.assertEqual(self.build["classe"], "Demon Hunter")
        self.assertEqual(self.build["todos_os_espacos"]["obrigatorios"][0]["modelo"], "+# Dexterity")
        self.assertEqual(self.build["fonte"]["link"], "https://maxroll.gg/d3/planner/345357607")
        self.assertEqual(self.build["nome"], "Sanc UE Multishot — Solo Push")

    def test_build_convertida_passa_na_conferencia(self):
        self.assertEqual(problemas_da_build(self.build), [])

    def test_escolher_perfil(self):
        self.assertEqual(nomes_dos_perfis(PLANNER), ["Solo Push", "Speed"])
        self.assertEqual(converter(PLANNER, DADOS, perfil=1)["fonte"]["perfil"], "Speed")
        with self.assertRaisesRegex(ErroMaxroll, "2 perfis"):
            converter(PLANNER, DADOS, perfil=5)

    def test_nome_do_arquivo(self):
        self.assertEqual(nome_do_arquivo(self.build), "sanc_ue_multishot")

    def test_runa_x_vira_sem_runa(self):
        # No Maxroll, "x" = habilidade sem runa (visto no Shadow Power do Shadow Impale).
        perfil = PERFIL | {"skills": [["shadowpower", "x"], ["multishot", "a"]]}
        build = converter(PLANNER | {"profiles": [perfil]}, DADOS)
        self.assertEqual([a["runa"] for a in build["habilidades"]["ativas"]], ["", "a"])
        self.assertEqual(problemas_da_build(build), [])

    def test_salvar_nunca_sobrescreve(self):
        with tempfile.TemporaryDirectory() as pasta:
            primeiro = salvar_build(self.build, Path(pasta))
            segundo = salvar_build(self.build, Path(pasta))
            self.assertEqual((primeiro.name, segundo.name), ("sanc_ue_multishot.json", "sanc_ue_multishot_2.json"))
            self.assertEqual(json.loads(primeiro.read_text(encoding="utf-8")), self.build)


class TestTiposDePlanner(unittest.TestCase):
    def test_planner_de_um_perfil_so(self):
        # Alguns planners guardam o perfil direto em "data", sem a lista "profiles".
        bruto = {"name": "Só um", "data": json.dumps(PERFIL)}
        planner = baixar_planner(1, abrir=resposta(bruto))
        self.assertEqual(nomes_dos_perfis(planner), ["Solo Push"])
        self.assertEqual(classe_do_planner(planner), "Demon Hunter")

    def test_seguidor_fica_de_fora(self):
        self.assertTrue(e_de_seguidor({"_nome": "GR Speed Enchantress"}))
        self.assertTrue(e_de_seguidor({"_nome": "T16 templar"}))
        self.assertFalse(e_de_seguidor({"_nome": "Sanc Shadow Impale"}))

    def test_classe_desconhecida(self):
        self.assertIsNone(classe_do_planner({"class": "paladin", "profiles": [{}]}))


def resposta(dados):
    return lambda pedido, timeout=None: io.BytesIO(json.dumps(dados).encode())


class TestBaixar(unittest.TestCase):
    def test_planner_com_data_em_texto(self):
        bruto = {"name": "Sanc UE Multishot", "data": json.dumps({"profiles": [PERFIL], "activeProfile": 0})}
        planner = baixar_planner(345357607, abrir=resposta(bruto))
        self.assertEqual((planner["_nome"], planner["_numero"]), ("Sanc UE Multishot", 345357607))

    def test_formato_estranho_avisa_que_o_site_mudou(self):
        with self.assertRaisesRegex(ErroMaxroll, "site pode ter mudado"):
            baixar_planner(1, abrir=resposta({"outra": "coisa"}))

    def test_build_que_nao_existe(self):
        def nao_achou(pedido, timeout=None):
            raise urllib.error.HTTPError(pedido.full_url, 404, "Not Found", {}, None)
        with self.assertRaisesRegex(ErroMaxroll, "não achou essa build"):
            baixar_planner(1, abrir=nao_achou)

    def test_data_json_lista_vira_dicionario_e_fica_guardado(self):
        bruto = {"items": [{"id": "P3_Unique_Ring_107", "name": "Ring of Royal Grandeur",
                            "ids": ["Unique_Ring_107_x1"], "muito": "mais coisa"}],
                 "legendaryGems": {"zei": {"name": "Zei's Stone of Vengeance", "effects": []}}}
        with tempfile.TemporaryDirectory() as pasta:
            dados = dados_do_planejador(Path(pasta), abrir=resposta(bruto))
            self.assertEqual(dados["items"]["P3_Unique_Ring_107"]["ids"], ["Unique_Ring_107_x1"])

            def sem_rede(pedido, timeout=None):
                raise AssertionError("não devia baixar de novo")
            self.assertEqual(dados_do_planejador(Path(pasta), abrir=sem_rede), dados)


if __name__ == "__main__":
    unittest.main()
