"""
Testes do módulo da API da Blizzard (src/blizzard.py).

Não usam internet nem as chaves do .env: uma "Blizzard de mentira" responde
os pedidos (FalsaBlizzard), com o mesmo formato das respostas reais.

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

from blizzard import (Blizzard, ErroBlizzard, chave_do_nome, itens_desconhecidos,  # noqa: E402
                      visual_da_build)

CLASSE_EN = {"slug": "demon-hunter", "name": "Demon Hunter", "skills": {
    "active": [{"slug": "multishot", "name": "Multishot", "icon": "demonhunter_multishot",
                "level": 22, "description": "Fire a massive volley"}],
    "passive": [{"slug": "archery", "name": "Archery", "icon": "demonhunter_passive_archery",
                 "level": 20, "description": "Gain a bonus"}]}}
CLASSE_PT = {"slug": "demon-hunter", "name": "Caçador de Demônios", "skills": {
    "active": [{"slug": "multishot", "name": "Tiro Múltiplo", "icon": "demonhunter_multishot",
                "level": 22, "description": "Dispara uma salva de flechas"}],
    "passive": [{"slug": "archery", "name": "Arquearia", "icon": "demonhunter_passive_archery",
                 "level": 20, "description": "Recebe um bônus"}]}}
RESPOSTAS = {
    "/d3/data/hero/demon-hunter?locale=en_US": CLASSE_EN,
    "/d3/data/hero/demon-hunter?locale=pt_BR": CLASSE_PT,
    "/d3/data/hero/demon-hunter/skill/multishot?locale=en_US": {"skill": {}, "runes": [
        {"slug": "full broadside", "type": "a", "name": "Full Broadside", "description": "More damage"},
        {"slug": "arsenal", "type": "c", "name": "Arsenal", "description": "Rockets"}]},
    "/d3/data/hero/demon-hunter/skill/multishot?locale=pt_BR": {"skill": {}, "runes": [
        {"slug": "full broadside", "type": "a", "name": "Banda de Artilharia", "description": "Mais dano"},
        {"slug": "arsenal", "type": "c", "name": "Arsenal", "description": "Foguetes"}]},
    "/d3/data/item-type?locale=en_US": [{"path": "item-type/ring"}, {"path": "item-type/gem"}],
    "/d3/data/item-type/ring?locale=en_US": [
        {"id": "Unique_Ring_021_x1", "name": "Litany of the Undaunted", "icon": "litany", "path": "item/litany"}],
    "/d3/data/item-type/gem?locale=en_US": [
        {"id": "Unique_Gem_012_x1", "name": "Zei's Stone of Vengeance", "icon": "zei", "path": "item/zei"}],
}


class FalsaBlizzard:
    """Faz o papel do urllib.request.urlopen: guarda os pedidos e responde."""

    def __init__(self, recusar_chaves=False):
        self.pedidos = []
        self.recusar_chaves = recusar_chaves

    def __call__(self, pedido, timeout=None):
        url = pedido.full_url
        self.pedidos.append(url)
        if "oauth.battle.net" in url:
            if self.recusar_chaves:
                raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
            return io.BytesIO(json.dumps({"access_token": "abc", "expires_in": 86399}).encode())
        caminho = url.split("api.blizzard.com", 1)[1]
        if caminho not in RESPOSTAS:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return io.BytesIO(json.dumps(RESPOSTAS[caminho]).encode())


class TestBlizzard(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.falsa = FalsaBlizzard()
        self.api = Blizzard("id", "segredo", Path(self.pasta.name), abrir=self.falsa)

    def test_sem_chaves_explica_o_que_fazer(self):
        api = Blizzard("", "", Path(self.pasta.name), abrir=self.falsa)
        with self.assertRaisesRegex(ErroBlizzard, "BLIZZARD_CLIENT_ID"):
            api.pegar("/d3/data/hero/demon-hunter")
        self.assertEqual(self.falsa.pedidos, [])  # nem tentou

    def test_chaves_recusadas(self):
        api = Blizzard("id", "errado", Path(self.pasta.name), abrir=FalsaBlizzard(recusar_chaves=True))
        with self.assertRaisesRegex(ErroBlizzard, "recusou as chaves"):
            api.pegar("/d3/data/hero/demon-hunter")

    def test_sem_internet(self):
        def sem_rede(pedido, timeout=None):
            raise urllib.error.URLError("sem rede")
        api = Blizzard("id", "segredo", Path(self.pasta.name), abrir=sem_rede)
        with self.assertRaisesRegex(ErroBlizzard, "internet"):
            api.pegar("/d3/data/hero/demon-hunter")

    def test_caminho_que_nao_existe(self):
        with self.assertRaisesRegex(ErroBlizzard, "não conhece"):
            self.api.pegar("/d3/data/hero/paladino")

    def test_um_token_so_e_cache_em_disco(self):
        self.api.pegar("/d3/data/hero/demon-hunter")
        self.api.pegar("/d3/data/hero/demon-hunter", "pt_BR")
        self.assertEqual(sum("oauth" in p for p in self.falsa.pedidos), 1)
        antes = len(self.falsa.pedidos)
        # Outro objeto, mesma pasta: vem do disco, sem pedir nada.
        outra = Blizzard("id", "segredo", Path(self.pasta.name), abrir=self.falsa)
        self.assertEqual(outra.pegar("/d3/data/hero/demon-hunter")["name"], "Demon Hunter")
        self.assertEqual(len(self.falsa.pedidos), antes)

    def test_habilidades_em_ingles_e_portugues(self):
        hab = self.api.habilidades("Demon Hunter")
        multi = hab["ativas"][0]
        self.assertEqual((multi["nome"], multi["nome_pt"]), ("Multishot", "Tiro Múltiplo"))
        self.assertEqual(multi["descricao_pt"], "Dispara uma salva de flechas")
        self.assertTrue(multi["icone"].endswith("/skills/64/demonhunter_multishot.png"))
        self.assertEqual(hab["passivas"][0]["nome_pt"], "Arquearia")

    def test_classe_que_nao_existe(self):
        with self.assertRaisesRegex(ErroBlizzard, "Opções"):
            self.api.habilidades("Paladin")

    def test_item_pelo_nome_do_jogo(self):
        zei = self.api.item("Zei’s Stone of Vengeance")  # apóstrofo curvo, como em sites
        self.assertEqual(zei["id"], "Unique_Gem_012_x1")
        self.assertTrue(zei["icone"].endswith("/items/large/zei.png"))
        self.assertIsNone(self.api.item("Anel Inventado"))

    def test_itens_desconhecidos_da_build(self):
        build = {"espacos": {"Finger": {"itens": ["Litany of the Undaunted", "Litany of the Undaunte"]}},
                 "gemas": ["zei's stone of vengeance"]}
        self.assertEqual(itens_desconhecidos(build, self.api.indice_de_itens()), ["Litany of the Undaunte"])


class TestVisualDaBuild(unittest.TestCase):
    """O que a janela recebe pra desenhar o boneco e a barra de habilidades."""

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.api = Blizzard("id", "segredo", Path(pasta.name), abrir=FalsaBlizzard())

    def test_itens_habilidade_com_runa_e_passiva(self):
        build = {"classe": "Demon Hunter",
                 "espacos": {"Finger": {"itens": ["Litany of the Undaunted", "Anel Inventado"]}},
                 "gemas": ["Zei's Stone of Vengeance"],
                 "habilidades": {"ativas": [{"habilidade": "multishot", "runa": "c"}],
                                 "passivas": ["archery"]}}
        v = visual_da_build(build, self.api)
        self.assertTrue(v["itens"]["Litany of the Undaunted"]["icone"].endswith("/litany.png"))
        self.assertIsNone(v["itens"]["Anel Inventado"]["icone"])  # sem ícone, mas aparece
        multi = v["habilidades"]["ativas"][0]
        self.assertEqual(multi["nome_pt"], "Tiro Múltiplo")
        self.assertEqual((multi["runa"]["nome_pt"], multi["runa"]["descricao_pt"]), ("Arsenal", "Foguetes"))
        self.assertEqual(v["habilidades"]["passivas"][0]["nome_pt"], "Arquearia")

    def test_habilidade_escrita_errada_aparece_sem_icone(self):
        build = {"classe": "Demon Hunter", "espacos": {},
                 "habilidades": {"ativas": [{"habilidade": "multishoot", "runa": "a"}], "passivas": []}}
        [h] = visual_da_build(build, self.api)["habilidades"]["ativas"]
        self.assertEqual((h["nome"], h["icone"], h["runa"]), ("multishoot", None, None))

    def test_build_sem_habilidades_nem_pede_a_classe(self):
        falsa = FalsaBlizzard()
        with tempfile.TemporaryDirectory() as pasta:
            api = Blizzard("id", "segredo", Path(pasta), abrir=falsa)
            v = visual_da_build({"classe": "Demon Hunter", "espacos": {}}, api)
        self.assertEqual(v["habilidades"], {"ativas": [], "passivas": []})
        self.assertFalse(any("/hero/" in p for p in falsa.pedidos))


class TestChaveDoNome(unittest.TestCase):
    def test_normaliza(self):
        self.assertEqual(chave_do_nome("Yang’s  Recurve "), "yang's recurve")
        self.assertEqual(chave_do_nome("Zei‘s Stone"), "zei's stone")
        self.assertEqual(chave_do_nome("Flecha Voraz É"), "flecha voraz e")


class TestBuildsDeVerdade(unittest.TestCase):
    """Se já existe o cache da Blizzard (dados/blizzard/, criado ao rodar
    `python src/blizzard.py`), confere os nomes das builds com ele."""

    def test_itens_das_builds_existem_no_jogo(self):
        arquivo = RAIZ / "dados" / "blizzard" / "indice_de_itens.json"
        if not arquivo.exists():
            self.skipTest("sem cache da Blizzard (rode python src/blizzard.py)")
        from avaliador import ler_builds
        indice = json.loads(arquivo.read_text(encoding="utf-8"))
        for build in ler_builds()[0]:
            with self.subTest(build["id"]):
                self.assertEqual(itens_desconhecidos(build, indice), [])


if __name__ == "__main__":
    unittest.main()
