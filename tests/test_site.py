"""
Testes do "Montar build" do site (docs/montar.html) e do caminho site -> app.

  - o link da build: abre o que o site gera e recusa o que não é dele, o que
    é grande demais (inclusive "bomba" de compressão) e build com problema;
  - o site tem o mesmo visual do app (docs/app.css = src/web/estilo.css);
  - docs/dados/jogo.json tem o que o site precisa, com afixos que o app aceita.

Rodar:
    python -m unittest discover tests
"""

import base64
import json
import sys
import unittest
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from avaliador import problemas_da_build  # noqa: E402
from link_do_site import ErroLinkDoSite, build_do_link, e_link_do_site  # noqa: E402

SITE = "https://ruthraaz.github.io/d3-companion/montar.html"

BUILD = {
    "formato": 1, "nome": "Teste UE", "apelido": "Teste UE", "classe": "Demon Hunter", "exige_ancient": False,
    "fonte": {"site": "montar"},
    "todos_os_espacos": {"obrigatorios": [{"modelo": "+# Dexterity", "rotulo": "Destreza"}]},
    "espacos": {"Head": {"itens": ["Accursed Visage"],
                         "desejaveis": [{"modelo": "@soquete", "rotulo": "Encaixe"}]},
                "Finger": {"itens": ["Focus", "Restraint"]}},
    "gemas": ["Zei's Stone of Vengeance"],
    "cubo": {"joia": "Ring of Royal Grandeur"},
    "habilidades": {"ativas": [{"habilidade": "multishot", "runa": "b"}], "passivas": []},
}


def link(dados, base=SITE) -> str:
    """Igual ao site: JSON -> deflate "cru" -> base64url sem "="."""
    texto = dados if isinstance(dados, bytes) else json.dumps(dados).encode()
    comprimido = zlib.compressobj(9, zlib.DEFLATED, -15)
    cru = comprimido.compress(texto) + comprimido.flush()
    return f"{base}#b=" + base64.urlsafe_b64encode(cru).decode().rstrip("=")


class TestLinkDoSite(unittest.TestCase):
    def test_abre_a_build_do_site(self):
        build = build_do_link(link(BUILD))
        self.assertEqual(build["espacos"]["Finger"]["itens"], ["Focus", "Restraint"])
        self.assertEqual(problemas_da_build(build), [])

    def test_reconhece_so_o_endereco_do_site(self):
        self.assertTrue(e_link_do_site(link(BUILD)))
        self.assertFalse(e_link_do_site("https://maxroll.gg/d3/planner/123"))
        self.assertFalse(e_link_do_site("https://ruthraaz.github.io.mal.com/d3-companion/montar.html#b=x"))

    def test_recusa_outro_endereco_ou_http(self):
        for ruim in (link(BUILD, "http://ruthraaz.github.io/d3-companion/montar.html"),
                     link(BUILD, "https://outro.github.io/d3-companion/montar.html"),
                     link(BUILD, "https://ruthraaz.github.io/outra/montar.html")):
            with self.subTest(ruim[:50]), self.assertRaises(ErroLinkDoSite):
                build_do_link(ruim)

    def test_recusa_link_sem_build_ou_cortado(self):
        for ruim in (SITE, SITE + "#b=", SITE + "#b=!!!", link(BUILD)[:-20], SITE + "#b=" + "A" * 30_000):
            with self.subTest(ruim[-30:]), self.assertRaises(ErroLinkDoSite):
                build_do_link(ruim)

    def test_recusa_bomba_de_compressao(self):
        # Poucos KB no link, 50 MB se abrisse tudo: para no limite e recusa.
        bomba = link(b'{"nome": "' + b"a" * 50_000_000 + b'"}')
        self.assertLess(len(bomba), 70_000)
        with self.assertRaises(ErroLinkDoSite):
            build_do_link(bomba[:len(SITE) + 3] + bomba[len(SITE) + 3:][:19_000])
        with self.assertRaises(ErroLinkDoSite):
            build_do_link(bomba)

    def test_recusa_o_que_nao_e_build(self):
        for ruim in ([1, 2], "texto", {"formato": 1, "nome": "x", "classe": "Paladino"},
                     BUILD | {"espacos": {"Hand": {"itens": ["Focus"]}}}):
            with self.subTest(str(ruim)[:40]), self.assertRaises(ErroLinkDoSite):
                build_do_link(link(ruim))

    def test_o_link_nao_escolhe_fonte_nem_comentario(self):
        build = build_do_link(link(BUILD | {"fonte": {"site": "maxroll", "link": "https://mal.com"},
                                            "_nota": "x", "apelido": ["nao", "texto"]}))
        self.assertEqual(build["fonte"], {"site": "montar"})
        self.assertNotIn("_nota", build)
        self.assertEqual(build["apelido"], "Teste UE")  # apelido que não é texto vira o nome


class TestSiteIgualAoApp(unittest.TestCase):
    def test_app_css_e_copia_do_estilo_do_app(self):
        app = (RAIZ / "src" / "web" / "estilo.css").read_text(encoding="utf-8").replace("\r\n", "\n")
        site = (RAIZ / "docs" / "app.css").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(site, app, "Rode: python ferramentas/dados_do_site.py --so-css (ou copie o arquivo).")


class TestDadosDoJogo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jogo = json.loads((RAIZ / "docs" / "dados" / "jogo.json").read_text(encoding="utf-8"))

    def test_tem_as_7_classes_com_habilidades_e_runas(self):
        self.assertEqual(len(self.jogo["classes"]), 7)
        for classe, c in self.jogo["classes"].items():
            with self.subTest(classe):
                self.assertGreater(len(c["ativas"]), 15)
                self.assertGreater(len(c["passivas"]), 15)
                self.assertTrue(all(len(h["r"]) == 5 for h in c["ativas"]))

    def test_todos_os_espacos_tem_itens(self):
        for espaco in ("Head", "Shoulders", "Neck", "Torso", "Hands", "Wrists", "Waist", "Legs", "Feet",
                       "Finger", "Weapon", "Off-Hand"):
            with self.subTest(espaco):
                self.assertGreater(len(self.jogo["espacos"].get(espaco, [])), 10)
        self.assertIn("Zei's Stone of Vengeance", {g["n"] for g in self.jogo["gemas"]})

    def test_build_com_tudo_que_o_site_oferece_passa_no_app(self):
        dh = self.jogo["classes"]["Demon Hunter"]
        build = {
            "formato": 1, "nome": "Tudo", "classe": "Demon Hunter",
            "todos_os_espacos": {"obrigatorios": [dh["atributo"]]},
            "espacos": {"Head": {"itens": [self.jogo["espacos"]["Head"][0]["n"]],
                                 "desejaveis": self.jogo["afixos"] + [dh["afixo"]]}},
            "gemas": [g["n"] for g in self.jogo["gemas"][:3]],
            "habilidades": {"ativas": [{"habilidade": h["s"], "runa": h["r"][0][0]} for h in dh["ativas"][:6]],
                            "passivas": [h["s"] for h in dh["passivas"][:4]]},
        }
        self.assertEqual(problemas_da_build(build), [])


if __name__ == "__main__":
    unittest.main()
