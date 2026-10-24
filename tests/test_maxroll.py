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
from maxroll import (ErroMaxroll, baixar_planner, builds_do_heroi, catalogo, classe_do_planner, converter,  # noqa: E402
                     dados_do_planejador, e_de_seguidor, guia_do_link, link_de_guia, planners_do_link,
                     salvar_build,
                     id_do_link, modelo_do_formato, nome_do_arquivo, nomes_dos_perfis, regras_do_item)

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
    # Formato igual ao "stats" do data.json do Maxroll (conferido em out/2026).
    "stats": {
        "dex": {"name": "Dexterity", "format": "+%d Dexterity", "secondary": False},
        "vit": {"name": "Vitality", "format": "+%d Vitality", "secondary": False},
        "chc": {"name": "Critical Hit Chance", "format": "Critical Hit Chance Increased by %.1f%%",
                "secondary": False},
        "chd": {"name": "Critical Hit Damage", "format": "Critical Hit Damage Increased by %d%%",
                "secondary": False},
        "wpnphy": {"name": "Damage", "format": "+%d-%d Damage", "secondary": False, "args": 2},
        "wpncol": {"name": "Cold Damage", "format": None, "secondary": False, "args": 2},
        "pickup": {"name": "Pickup Radius", "format": "Increases Gold and Health pickup by %d yards.",
                   "secondary": True},
        "dura": {"name": "Durability", "format": None, "secondary": False},
    },
}

PERFIL = {
    "name": "Solo Push", "class": "demonhunter",
    "skills": [["entanglingshot", "b"], ["multishot", "a"]],
    "passives": ["culltheweak", "ambush"],
    "kanai": {"weapon": "P69_Unique_Bow_102", "jewelry": "Unique_Ring_107_x1"},
    "items": {
        "head": {"id": "Unique_Helm_Set_03_p2", "gems": [[9, "topaz"]]},
        "leftfinger": {"id": "Unique_Ring_Set_001_x1", "gems": [["trapped", 150]],
                       "stats": {"dex": {}, "chc": {}, "sockets": {}}},
        "rightfinger": {"id": "Unique_Ring_Set_002_x1", "gems": [["zei", 150]],
                        "stats": {"chc": {}, "chd": {}, "sockets": {}}},
        "mainhand": {"id": "P61_Unique_Bow_104_x1", "stats": {"wpncol": {}, "sockets": {}}},
        "waist": {"id": "Item_Que_Nao_Existe"},
    },
}
PLANNER = {"_nome": "Sanc UE Multishot", "_numero": 345357607, "activeProfile": 0, "class": "demonhunter",
           "profiles": [PERFIL, {"name": "Speed", "class": "demonhunter", "items": {}}]}

HABILIDADES = {
    "ativas": [{"slug": "entangling-shot", "nome": "Entangling Shot"},
               {"slug": "multishot", "nome": "Multishot", "nome_pt": "Tiro Múltiplo"}],
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

    def test_fonte_guarda_o_guia(self):
        guia = "https://maxroll.gg/d3/guides/ue-multishot-demon-hunter-guide"
        build = converter(PLANNER | {"_guia": guia}, DADOS)
        self.assertEqual(build["fonte"]["guia"], guia)
        self.assertNotIn("guia", self.build["fonte"])  # link de planner: sem guia

    def test_salvar_nunca_sobrescreve(self):
        with tempfile.TemporaryDirectory() as pasta:
            primeiro = salvar_build(self.build, Path(pasta))
            segundo = salvar_build(self.build, Path(pasta))
            self.assertEqual((primeiro.name, segundo.name), ("sanc_ue_multishot.json", "sanc_ue_multishot_2.json"))
            self.assertEqual(json.loads(primeiro.read_text(encoding="utf-8")), self.build)


class TestCatalogo(unittest.TestCase):
    MAPA = """<urlset>
      <url><loc>https://maxroll.gg/d3/category/guides/wizard</loc></url>
      <url><loc>https://maxroll.gg/d3/guides/shadow-impale-demon-hunter-guide</loc></url>
      <url><loc>https://maxroll.gg/d3/guides/lod-skeletal-mage-rat-necromancer</loc></url>
      <url><loc>https://maxroll.gg/d3/guides/support-zbarb-guide</loc></url>
      <url><loc>https://maxroll.gg/d3/guides/aov-fist-of-the-heavens-crusader-guide</loc></url>
      <url><loc>https://maxroll.gg/d3/resources/season-start-1-70-leveling-guide</loc></url>
    </urlset>"""

    def abrir(self, pedido, timeout=None):
        self.pedidos += 1
        return io.BytesIO(self.MAPA.encode())

    def setUp(self):
        self.pedidos = 0
        self.pasta = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.pasta.cleanup()

    def test_nome_e_classe_saem_do_link(self):
        self.assertEqual(guia_do_link("https://maxroll.gg/d3/guides/shadow-impale-demon-hunter-guide"),
                         {"link": "https://maxroll.gg/d3/guides/shadow-impale-demon-hunter-guide",
                          "titulo": "Shadow Impale", "classe": "Demon Hunter"})
        self.assertEqual(guia_do_link("https://maxroll.gg/d3/guides/vyr-chantodo-archon-wod-wizard-guide")["titulo"],
                         "Vyr Chantodo Archon WoD")
        self.assertIsNone(guia_do_link("https://maxroll.gg/d3/guides/algo-sem-classe-guide"))

    def test_lista_so_guias_de_classe_em_ordem(self):
        guias = catalogo(Path(self.pasta.name), self.abrir)
        self.assertEqual([(g["classe"], g["titulo"]) for g in guias], [
            ("Barbarian", "Suporte"), ("Crusader", "AoV Fist of the Heavens"),
            ("Demon Hunter", "Shadow Impale"), ("Necromancer", "LoD Skeletal Mage Rat"),
        ])

    def test_guarda_e_so_busca_de_novo_no_outro_dia_ou_se_pedir(self):
        pasta = Path(self.pasta.name)
        catalogo(pasta, self.abrir)
        catalogo(pasta, self.abrir)
        self.assertEqual(self.pedidos, 1)
        catalogo(pasta, self.abrir, atualizar=True)
        self.assertEqual(self.pedidos, 2)

    def test_sem_internet_usa_o_guardado(self):
        pasta = Path(self.pasta.name)
        guias = catalogo(pasta, self.abrir)

        def sem_rede(pedido, timeout=None):
            raise urllib.error.URLError("sem rede")
        self.assertEqual(catalogo(pasta, sem_rede, atualizar=True), guias)
        with tempfile.TemporaryDirectory() as vazia:
            with self.assertRaisesRegex(ErroMaxroll, "sem internet"):
                catalogo(Path(vazia), sem_rede)


class TestAfixos(unittest.TestCase):
    """Os afixos que o guia escolheu viram as regras desejáveis (o "Crítico ✓" do selo)."""

    HAB = {"multishot": {"nome": "Multishot", "nome_pt": "Tiro Múltiplo"}}

    def regras(self, *chaves, na_arma=False):
        return regras_do_item({c: {} for c in chaves}, DADOS, "dex", self.HAB, na_arma=na_arma)

    def test_formato_vira_modelo_do_parser(self):
        self.assertEqual(modelo_do_formato("Critical Hit Chance Increased by %.1f%%"),
                         "Critical Hit Chance Increased by #%")
        self.assertEqual(modelo_do_formato("+%d-%d Damage"), "+#-# Damage")

    def test_encaixe_critico_e_rotulos(self):
        self.assertEqual(self.regras("sockets", "chc"), [
            {"modelo": "@soquete", "rotulo": "Encaixe"},
            {"modelo": "Critical Hit Chance Increased by #%", "rotulo": "Crítico"},
        ])

    def test_atributo_principal_secundario_e_durabilidade_ficam_de_fora(self):
        # Destreza já é obrigatória em todo espaço; raio de coleta e durabilidade não importam.
        self.assertEqual(self.regras("dex", "pickup", "dura", "inventado"), [])

    def test_dano_de_habilidade_com_sufixo_da_classe(self):
        self.assertEqual(self.regras("skill_demonhunter_multishot"),
                         [{"modelo": "Increases Multishot Damage by #% *", "rotulo": "Dano de Tiro Múltiplo"}])

    def test_dano_elemental_da_arma_tem_faixa(self):
        self.assertEqual(self.regras("wpncol", na_arma=True),
                         [{"modelo": "+#-# Cold Damage", "rotulo": "Dano da arma"}])
        self.assertEqual(self.regras("wpnphy"), [{"modelo": "+#-# Damage", "rotulo": "Dano mín–máx"}])

    def test_aneis_juntam_sem_repetir(self):
        build = converter(PLANNER, DADOS, HABILIDADES)
        self.assertEqual([r["rotulo"] for r in build["espacos"]["Finger"]["desejaveis"]],
                         ["Crítico", "Encaixe", "Dano crítico"])
        self.assertEqual([r["rotulo"] for r in build["espacos"]["Weapon"]["desejaveis"]],
                         ["Dano da arma", "Encaixe"])


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

    def test_guia_so_traz_builds_da_classe_dele(self):
        # O guia de Arachyr Spiders (Witch Doctor) mostra um "DH Speed" de Demon Hunter no meio.
        wd = {"_nome": "Arachyr Spiders S27", "class": "witchdoctor", "profiles": [{}]}
        dh = {"_nome": "DH Speed (non-Resource)", "class": "demonhunter", "profiles": [{}]}
        seguidor = {"_nome": "GR Speed Enchantress", "class": "wizard", "profiles": [{}]}
        guia = "https://maxroll.gg/d3/guides/arachyr-corpse-spiders-witch-doctor-guide"
        self.assertEqual(builds_do_heroi([wd, dh, seguidor], guia), [wd])
        # Link de planner: não tem classe do guia, vale qualquer herói.
        self.assertEqual(builds_do_heroi([dh], "https://maxroll.gg/d3/planner/1"), [dh])

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
