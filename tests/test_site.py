"""
Testes do "Montar build" (aba Montar do app e docs/montar.html) e das dicas.

  - o link da build: abre o que o site gera e recusa o que não é dele, o que
    é grande demais (inclusive "bomba" de compressão) e build com problema;
  - o site usa os mesmos arquivos do app (docs/ tem cópias em dia);
  - dados/jogo.json tem o que o montador precisa, com afixos que o app aceita;
  - dados/dicas.json (o que cada item faz) sai da API só como texto;
  - a aba Montar do app grava, altera só o que foi montado e recusa build ruim.

Rodar:
    python -m unittest discover tests
"""

import base64
import datetime
import functools
import json
import re
import sys
import tempfile
import unittest
import zlib
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "ferramentas"))

import dados_do_site  # noqa: E402
import janela  # noqa: E402
from avaliador import problemas_da_build  # noqa: E402
from link_do_site import ErroLinkDoSite, build_do_link, e_link_do_site  # noqa: E402
from maxroll import regravar_build, salvar_build  # noqa: E402

SITE = "https://ruthraaz.github.io/d3-companion/montar.html"
DADOS = RAIZ / "src" / "web" / "dados"

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


def ler_json(arquivo: Path):
    return json.loads(arquivo.read_text(encoding="utf-8"))


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
    def test_copias_do_site_estao_em_dia(self):
        for origem, destino in dados_do_site.COPIAS.items():
            with self.subTest(destino.name):
                app = origem.read_text(encoding="utf-8").replace("\r\n", "\n")
                site = destino.read_text(encoding="utf-8").replace("\r\n", "\n")
                self.assertEqual(site, app, "Rode: python ferramentas/dados_do_site.py --so-copiar")

    def test_paginas_carregam_o_montador_e_a_dica(self):
        for pagina in (RAIZ / "src" / "web" / "index.html", RAIZ / "docs" / "montar.html"):
            with self.subTest(pagina.name):
                texto = pagina.read_text(encoding="utf-8")
                for arquivo in ("dica.js", "montar.js", "montar.css"):
                    self.assertIn(arquivo, texto)
                self.assertIn("data-montador=", texto)
                self.assertIn('data-m="detalhe"', texto)


class TestSegurancaDoSite(unittest.TestCase):
    """O site é público: cada página com CSP, nada de script inline, nenhuma
    imagem do jogo e a prévia de link apontando pra imagem própria."""

    PAGINAS = sorted((RAIZ / "docs").rglob("*.html"))
    IMAGENS_PERMITIDAS = {"img/janela.png", "img/compartilhar.png", "favicon.svg"}

    def test_toda_pagina_tem_csp_rigida(self):
        self.assertGreaterEqual(len(self.PAGINAS), 3)
        for pagina in self.PAGINAS:
            with self.subTest(pagina.name):
                html = pagina.read_text(encoding="utf-8")
                csp = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', html)
                self.assertIsNotNone(csp, "página sem CSP")
                csp = csp.group(1)
                for regra in ("object-src 'none'", "base-uri 'none'", "form-action 'none'"):
                    self.assertIn(regra, csp)
                self.assertNotIn("unsafe-inline", csp)
                self.assertNotIn("unsafe-eval", csp)
                self.assertIn('<meta name="referrer" content="no-referrer">', html)

    def test_sem_script_inline_nem_de_fora(self):
        for pagina in self.PAGINAS:
            with self.subTest(pagina.name):
                html = pagina.read_text(encoding="utf-8")
                for atributos, corpo in re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S):
                    src = re.search(r'src="([^"]+)"', atributos)
                    self.assertIsNotNone(src, "script inline")
                    self.assertEqual(corpo.strip(), "")
                    self.assertNotRegex(src.group(1), r"^(https?:)?//", "script de outro site")
                self.assertNotRegex(html, r"<[^>]+\son[a-z]+\s*=", "evento inline (onclick=...)")
                self.assertNotRegex(html, r"<[^>]+\sstyle\s*=", "style inline (a CSP bloqueia)")
                for link in re.findall(r"<a\s[^>]*target=[^>]*>", html):
                    self.assertIn("noopener", link)

    def test_js_do_site_nao_monta_html(self):
        for js in (RAIZ / "docs").glob("*.js"):
            with self.subTest(js.name):
                texto = js.read_text(encoding="utf-8")
                for perigo in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
                    self.assertNotIn(perigo, texto)

    def test_nenhuma_imagem_do_jogo_no_site(self):
        imagens = {str(p.relative_to(RAIZ / "docs")).replace("\\", "/") for p in (RAIZ / "docs").rglob("*")
                   if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"}}
        self.assertEqual(imagens - self.IMAGENS_PERMITIDAS, set(),
                         "imagem nova no site: confira se não é print ou arte do jogo e libere aqui")

    def test_previa_do_link_com_imagem_propria(self):
        for pagina in (RAIZ / "docs" / "index.html", RAIZ / "docs" / "pt" / "index.html", RAIZ / "docs" / "montar.html"):
            with self.subTest(str(pagina.relative_to(RAIZ))):
                html = pagina.read_text(encoding="utf-8")
                imagem = re.search(r'property="og:image" content="([^"]+)"', html).group(1)
                self.assertTrue(imagem.startswith("https://ruthraaz.github.io/d3-companion/"))
                self.assertTrue((RAIZ / "docs" / imagem.split("/d3-companion/", 1)[1]).is_file())
                self.assertIn('name="twitter:card" content="summary_large_image"', html)
                self.assertIn('rel="canonical"', html)

    def test_security_txt_valido(self):
        texto = (RAIZ / "docs" / ".well-known" / "security.txt").read_text(encoding="utf-8")
        self.assertIn("Contact: https://github.com/Ruthraaz/d3-companion/security/advisories/new", texto)
        vence = re.search(r"^Expires: (\S+)$", texto, re.M).group(1)
        self.assertGreater(vence, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertNotIn("@", texto, "sem e-mail pessoal no site")


class TestDadosDoJogo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jogo = ler_json(DADOS / "jogo.json")

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


class TestDicas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dicas = ler_json(DADOS / "dicas.json")
        cls.jogo = ler_json(DADOS / "jogo.json")

    def test_quase_todo_item_do_montador_tem_dica(self):
        nomes = {i["n"] for lista in self.jogo["espacos"].values() for i in lista}
        self.assertGreater(len(nomes & set(self.dicas["itens"])), len(nomes) * 0.95)
        for g in self.jogo["gemas"]:
            with self.subTest(g["n"]):
                self.assertTrue(self.dicas["itens"][g["n"]].get("p"), "gema sem o que ela faz")

    def test_so_texto_sem_html(self):
        texto = json.dumps(self.dicas, ensure_ascii=False)
        self.assertNotIn("<", texto)
        self.assertNotIn("d3-color", texto)

    def test_set_tem_os_bonus(self):
        mascara = self.dicas["itens"]["The Shadow's Mask"]
        bonus = self.dicas["sets"][mascara["s"]]
        self.assertEqual(len(bonus), 3)
        self.assertTrue(all(b.startswith("Conjunto (") for b in bonus))

    def test_leitura_do_html_da_blizzard(self):
        arma = {"attributes": {"secondary": [{"textHtml":
            '<span class="d3-color-ffff8000"> O dano aumenta em <span class="d3-color-magic">344%</span>.</span> '
            '<span class="d3-color-ffff0000">(Somente Caçador de Demônios)</span> '
            '<span class="d3-color-ff9b9b9b">[300 - 375]%</span>'}]}}
        self.assertEqual(dados_do_site.poderes(arma, e_gema=False),
                         ["O dano aumenta em 344%. (no jogo: [300 - 375]%) · Somente Caçador de Demônios"])
        gema = {"attributes": {"secondary": [{"textHtml":
            '<span class="d3-color-ffff8000">Aumenta em <span class="d3-color-magic"> 15,00%</span> o dano.</span> '
            '<span class="d3-color-ff9b9b9b">15,00%</span>'}]}}
        self.assertEqual(dados_do_site.poderes(gema, e_gema=True), ["Aumenta em 15,00% o dano."])
        anel = {"attributes": {"secondary": [
            {"textHtml": '<span class="d3-color-ff6969ff">Engastes (1)</span>'},
            {"textHtml": '<span class="d3-color-ff6969ff">Reduz o número de itens do set em 1.</span>'}]}}
        self.assertEqual(dados_do_site.poderes(anel, e_gema=False), ["Reduz o número de itens do set em 1."])
        conjunto = {"setDescriptionHtml": '<span class="d3-color-ff00ff00">Conjunto (2):<br />    '
                    '<span class="tooltip-icon-bullet"></span> Ganha <b>60%</b> de dano.</span><br />'}
        self.assertEqual(dados_do_site.bonus_do_set(conjunto), ["Conjunto (2): Ganha 60% de dano."])


class TestMontarNoApp(unittest.TestCase):
    """Api.salvar_montada e companhia, gravando numa pasta temporária."""

    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self._pasta.cleanup)
        self.pasta = Path(self._pasta.name)
        self.api = janela.Api.__new__(janela.Api)  # sem overlay nem Blizzard
        for nome, funcao in (("salvar_build", salvar_build), ("regravar_build", regravar_build)):
            remendo = mock.patch.object(janela, nome, functools.partial(funcao, pasta=self.pasta))
            remendo.start()
            self.addCleanup(remendo.stop)

    def ler(self, id_build):
        return ler_json(self.pasta / f"{id_build}.json")

    def test_salva_nova_e_depois_altera_a_mesma(self):
        r = self.api.salvar_montada(BUILD | {"fonte": {"site": "maxroll"}, "_x": 1})
        self.assertNotIn("erro", r)
        self.assertEqual(self.ler(r["id"])["fonte"], {"site": "montar"})
        self.assertNotIn("_x", self.ler(r["id"]))
        r2 = self.api.salvar_montada(BUILD | {"apelido": "Outro nome"}, r["id"])
        self.assertEqual(r2, r)
        self.assertEqual(self.ler(r["id"])["apelido"], "Outro nome")
        self.assertEqual(len(list(self.pasta.glob("*.json"))), 1)

    def test_nao_altera_build_do_maxroll(self):
        importada = salvar_build(BUILD | {"apelido": "Do Maxroll", "fonte": {"site": "maxroll"}}, self.pasta)
        r = self.api.salvar_montada(BUILD, importada.stem)
        self.assertIn("erro", r)
        self.assertEqual(self.ler(importada.stem)["fonte"], {"site": "maxroll"})

    def test_recusa_id_estranho_build_ruim_e_grande_demais(self):
        self.assertIn("erro", self.api.salvar_montada(BUILD, "../segredo"))
        self.assertIn("erro", self.api.salvar_montada(BUILD | {"espacos": {"Hand": {"itens": ["Focus"]}}}))
        self.assertIn("erro", self.api.salvar_montada("isso não é build"))
        self.assertIn("erro", self.api.salvar_montada(BUILD | {"nome": "a" * 300_000}))
        self.assertEqual(list(self.pasta.glob("*.json")), [])

    def test_dados_do_jogo_so_os_arquivos_conhecidos(self):
        self.assertIn("classes", self.api.dados_do_jogo("jogo"))
        self.assertIn("itens", self.api.dados_do_jogo("dicas"))
        self.assertIn("itens", self.api.dados_do_jogo("dicas.en"))
        self.assertEqual(self.api.dados_do_jogo("en")["Salvar no app"], "Save to app")
        for estranho in ("../../.env", "dicas.en/../../.env", "EN", ""):
            self.assertIn("erro", self.api.dados_do_jogo(estranho))


class TestIdioma(unittest.TestCase):
    """Inglês e português: o texto do código é em português e dados/en.json diz
    como fica em inglês. Frase nova sem tradução aparece em português, então
    o teste pega antes."""

    @classmethod
    def setUpClass(cls):
        cls.en = ler_json(DADOS / "en.json")

    @staticmethod
    def frases_do_js(caminho):
        texto = caminho.read_text(encoding="utf-8")
        return {json.loads(f'"{m}"') for m in re.findall(r'\bt\("((?:[^"\\]|\\.)*)"', texto)}

    @staticmethod
    def frases_do_html(caminho):
        """O que Idioma.aplicar() traduz: os textos de dentro de quem tem data-t
        (sem espaço sobrando) e os atributos de texto dele."""
        frases = set()
        vazios = {"input", "meta", "link", "br", "img", "hr", "source"}

        class Leitor(HTMLParser):
            pilha = []

            def handle_starttag(self, tag, atributos):
                atributos = dict(atributos)
                marcado = "data-t" in atributos and "data-trocar-idioma" not in atributos
                if marcado:
                    for nome in ("placeholder", "title", "aria-label", "alt", "content"):
                        if atributos.get(nome):
                            frases.add(atributos[nome])
                if tag not in vazios:
                    self.pilha.append(marcado)

            def handle_endtag(self, tag):
                if tag not in vazios and self.pilha:
                    self.pilha.pop()

            def handle_data(self, dados):
                if self.pilha and self.pilha[-1] and dados.strip():
                    frases.add(re.sub(r"\s+", " ", dados.strip()))

        Leitor().feed(caminho.read_text(encoding="utf-8"))
        return frases

    def test_toda_frase_do_js_tem_traducao(self):
        for js in (RAIZ / "src" / "web" / "montar.js", RAIZ / "src" / "web" / "app.js"):
            with self.subTest(js.name):
                faltam = sorted(self.frases_do_js(js) - set(self.en))
                self.assertEqual(faltam, [], "ponha em src/web/dados/en.json")

    def test_toda_frase_marcada_no_html_tem_traducao(self):
        for pagina in (RAIZ / "docs" / "montar.html", RAIZ / "src" / "web" / "index.html"):
            with self.subTest(pagina.name):
                frases = self.frases_do_html(pagina)
                self.assertGreater(len(frases), 10)
                faltam = sorted(frases - set(self.en))
                self.assertEqual(faltam, [], "ponha em src/web/dados/en.json")

    def test_nomes_do_montador_tem_traducao(self):
        texto = (RAIZ / "src" / "web" / "montar.js").read_text(encoding="utf-8")
        for bloco in ("NOMES", "PARTES_DO_CUBO", "LUGARES_DAS_HABILIDADES", "PARAGON"):
            corpo = re.search(rf"^const {bloco} = (.*?);$", texto, re.M | re.S).group(1)
            for frase in re.findall(r'"([^"]+)"', corpo):
                if frase in {"Off-Hand", "1", "2", "3", "4"} or not re.search(r"[a-zà-ú]", frase):
                    continue
                if bloco == "NOMES" and not re.search(r":\s*$", corpo.split(f'"{frase}"')[0]):
                    continue  # é a chave (Head, Shoulders...), não o nome mostrado
                with self.subTest(frase):
                    self.assertIn(frase, self.en)
        jogo = ler_json(DADOS / "jogo.json")
        for a in jogo["afixos"] + [c["atributo"] for c in jogo["classes"].values()]:
            with self.subTest(a["rotulo"]):
                self.assertIn(a["rotulo"], self.en)

    def test_traducao_mantem_as_variaveis(self):
        for pt, en in self.en.items():
            with self.subTest(pt):
                self.assertIsInstance(en, str)
                self.assertTrue(en.strip())
                self.assertEqual(sorted(re.findall(r"\{\w+\}", pt)), sorted(re.findall(r"\{\w+\}", en)))
                self.assertNotIn("<", en)

    def test_dicas_em_ingles(self):
        dicas = ler_json(DADOS / "dicas.en.json")
        mascara = dicas["itens"]["The Shadow's Mask"]
        self.assertEqual(mascara["n"], "The Shadow's Mask")
        self.assertTrue(all(b.startswith("(") and "Set" in b for b in dicas["sets"][mascara["s"]]))
        self.assertNotIn("<", json.dumps(dicas, ensure_ascii=False))

    def test_pagina_inicial_nos_dois_idiomas(self):
        en = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
        pt = (RAIZ / "docs" / "pt" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="en">', en)
        self.assertIn('<html lang="pt-BR">', pt)
        for html in (en, pt):
            self.assertIn('hreflang="en" href="https://ruthraaz.github.io/d3-companion/"', html)
            self.assertIn('hreflang="pt-BR" href="https://ruthraaz.github.io/d3-companion/pt/"', html)
        # A cópia em pt/ usa os arquivos da raiz.
        for caminho in re.findall(r'(?:src|href)="([^"#:]+)"', pt):
            with self.subTest(caminho):
                self.assertTrue((RAIZ / "docs" / "pt" / caminho).resolve().exists(), caminho)
        self.assertIn("https://ruthraaz.github.io/d3-companion/pt/",
                      (RAIZ / "docs" / "sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
