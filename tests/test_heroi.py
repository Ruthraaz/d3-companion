"""
Testes do herói da BattleTag (aba "Meu herói").

Sem internet: os dados da Blizzard aqui são inventados no formato da API de
perfil (nada de perfil de jogador de verdade no repositório).

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

from avaliador import avaliar, carregar_builds  # noqa: E402
from blizzard import ErroBlizzard, NaoEncontrado  # noqa: E402
from builds_dos_testes import PASTA_DOS_TESTES  # noqa: E402
from config import validar  # noqa: E402
from heroi import comparar, conta_da_battletag, heroi, herois, item_do_perfil  # noqa: E402

UNHALLOWED = next(b for b in carregar_builds(PASTA_DOS_TESTES) if b["id"] == "unhallowed_multidisparo")

# Luvas no formato da API de perfil (inventadas, iguais às da dica do jogo nos testes do OCR).
LUVAS = {
    "name": "Fiendish Grips",
    "typeName": "Ancient Set Gloves",
    "icon": "unique_gloves_set_14_x1_demonhunter_male",
    "attributes": {
        "primary": ["+732 Dexterity", "+722 Vitality", "Attack Speed Increased by 5.0%",
                    "Critical Hit Chance Increased by 9.0%",
                    "Caldesann's Despair Rank 100 adds +500 Dexterity"],
        "secondary": ["+160 Cold Resistance"],
    },
    "attributesHtml": {
        "primary": ["<span>+732 Dexterity</span>", "<span>+722 Vitality</span>",
                    "<span>Attack Speed Increased by 5.0%</span>",
                    '<span class="tooltip-icon-enchant">Critical Hit Chance Increased by 9.0%</span>',
                    "<span>Caldesann's Despair</span>"],
    },
    "openSockets": 0,
}


class TestBattleTag(unittest.TestCase):
    def test_vira_conta_da_api(self):
        self.assertEqual(conta_da_battletag("Jogador#1234"), "Jogador-1234")
        self.assertEqual(conta_da_battletag("  Jogador # 12345 "), "Jogador-12345")
        self.assertEqual(conta_da_battletag("Jogador-1234"), "Jogador-1234")

    def test_sem_numero_da_erro_claro(self):
        for ruim in ("Jogador", "Jogador#", "#1234", "", "um nome muito comprido#1234"):
            with self.assertRaises(ErroBlizzard, msg=ruim):
                conta_da_battletag(ruim)

    def test_config_valida_a_battletag(self):
        self.assertIsNone(validar("BATTLETAG", ""))  # vazio = não usa a aba
        self.assertIsNone(validar("BATTLETAG", "Jogador#1234"))
        self.assertIn("BattleTag", validar("BATTLETAG", "Jogador"))


class PerfilFalso:
    """Faz o papel da Blizzard: perfis inventados por região; o resto é 404."""

    def __init__(self, perfis, erro=None):
        self.perfis, self.erro, self.pedidos = perfis, erro, []

    def pegar(self, caminho, locale="en_US", guardar=True, regiao="us"):
        self.pedidos.append((regiao, caminho))
        if self.erro:
            raise self.erro
        if regiao not in self.perfis:
            raise NaoEncontrado("404")
        return self.perfis[regiao]


def _heroi(id_, nome, atualizado):
    return {"id": id_, "name": nome, "class": "demon-hunter", "level": 70, "last-updated": atualizado}


class TestRegioes(unittest.TestCase):
    def test_procura_nas_quatro_e_junta(self):
        api = PerfilFalso({"us": {"heroes": [_heroi(1, "Americana", 100)]},
                           "eu": {"heroes": [_heroi(1, "Europeia", 200)]}})
        lista = herois(api, "Jogador#1234")
        self.assertEqual([(h["regiao"], h["nome"]) for h in lista], [("eu", "Europeia"), ("us", "Americana")])
        self.assertEqual(sorted(r for r, _ in api.pedidos), ["eu", "kr", "tw", "us"])

    def test_so_europa(self):
        lista = herois(PerfilFalso({"eu": {"heroes": [_heroi(7, "Europeia", 1)]}}), "Jogador#1234")
        self.assertEqual([(h["regiao"], h["id"]) for h in lista], [("eu", 7)])

    def test_nenhuma_regiao(self):
        with self.assertRaisesRegex(NaoEncontrado, "nenhuma região"):
            herois(PerfilFalso({}), "Jogador#1234")

    def test_sem_internet_nao_vira_battletag_errada(self):
        with self.assertRaisesRegex(ErroBlizzard, "internet"):
            herois(PerfilFalso({}, erro=ErroBlizzard("Está sem internet?")), "Jogador#1234")

    def test_heroi_pede_na_regiao_dele(self):
        api = PerfilFalso({"kr": {"id": 9, "name": "Coreana", "class": "demon-hunter"}})
        self.assertEqual(heroi(api, "Jogador#1234", 9, "kr")["nome"], "Coreana")
        self.assertEqual({r for r, _ in api.pedidos}, {"kr"})


class TestItemDoPerfil(unittest.TestCase):
    def setUp(self):
        self.item = item_do_perfil(LUVAS, "Hands")

    def test_qualidade_tipo_e_espaco(self):
        self.assertEqual((self.item["qualidade"], self.item["tipo"], self.item["slot"]),
                         ("Ancient Set", "Gloves", "Hands"))

    def test_primal(self):
        item = item_do_perfil({**LUVAS, "typeName": "Primal Ancient Legendary Bow"}, "Weapon")
        self.assertEqual((item["qualidade"], item["tipo"]), ("Primal Ancient Legendary", "Bow"))

    def test_aumento_do_cubo_nao_e_afixo(self):
        self.assertEqual(len(self.item["primarios"]), 4)
        self.assertFalse(any("Caldesann" in a["texto"] for a in self.item["primarios"]))

    def test_afixo_trocado_no_mistico(self):
        self.assertEqual(self.item["encantado"], "Critical Hit Chance Increased by 9.0%")

    def test_soquetes_contam_as_gemas(self):
        item = item_do_perfil({**LUVAS, "openSockets": 1, "gems": [{"item": {"name": "Zei"}}]}, "Neck")
        self.assertEqual(item["soquetes"], 2)


class TestDicaDoMistico(unittest.TestCase):
    def test_sem_trocar_no_mistico_sugere_o_que_sobra(self):
        item = {**item_do_perfil(LUVAS, "Hands"), "encantado": None}
        self.assertEqual(avaliar(item, UNHALLOWED)["sobrando"], ["Attack Speed Increased by 5.0%"])

    def test_ja_trocou_um_que_serve_nao_sugere_nada(self):
        # O Crítico já foi trocado no Místico (e serve): a Velocidade não pode mais ser trocada.
        self.assertEqual(avaliar(item_do_perfil(LUVAS, "Hands"), UNHALLOWED)["sobrando"], [])

    def test_ja_trocou_o_que_sobra_pode_trocar_de_novo(self):
        item = {**item_do_perfil(LUVAS, "Hands"), "encantado": "Attack Speed Increased by 5.0%"}
        self.assertEqual(avaliar(item, UNHALLOWED)["sobrando"], ["Attack Speed Increased by 5.0%"])


class TestComparar(unittest.TestCase):
    BUILD = {
        "classe": "Demon Hunter", "espacos": {},
        "habilidades": {
            "ativas": [{"habilidade": "multishot", "runa": "a"}, {"habilidade": "vengeance", "runa": "c"},
                       {"habilidade": "companion", "runa": "e"}],
            "passivas": ["awareness", "ambush"],
        },
    }
    HEROI = {
        "classe": "Demon Hunter", "itens": {},
        "habilidades": {
            "ativas": [{"habilidade": "multishot", "runa": "a"}, {"habilidade": "vengeance", "runa": "b"},
                       {"habilidade": "vault", "runa": "d"}],
            "passivas": ["awareness", "archery"],
        },
    }

    def test_habilidades_ok_runa_e_falta(self):
        r = comparar(self.HEROI, self.BUILD)
        self.assertEqual([(a["habilidade"], a["estado"]) for a in r["habilidades"]["ativas"]],
                         [("multishot", "ok"), ("vengeance", "runa"), ("companion", "falta")])
        self.assertEqual(r["habilidades"]["ativas"][1]["runa_do_heroi"], "b")
        self.assertEqual([p["estado"] for p in r["habilidades"]["passivas"]], ["ok", "falta"])
        self.assertEqual(r["habilidades"]["fora_da_build"], ["vault", "archery"])
        self.assertTrue(r["classe_igual"])

    def test_itens_usam_o_mesmo_avaliador_do_f8(self):
        heroi = {**self.HEROI, "itens": {"hands": item_do_perfil(LUVAS, "Hands")}}
        r = comparar(heroi, UNHALLOWED)
        self.assertEqual(r["itens"][0]["espaco"], "Hands")
        self.assertTrue(r["itens"][0]["resultado"]["bate"])

    def test_outra_classe(self):
        self.assertFalse(comparar({**self.HEROI, "classe": "Wizard"}, self.BUILD)["classe_igual"])


if __name__ == "__main__":
    unittest.main()
