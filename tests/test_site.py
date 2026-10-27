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

import ast
import base64
import datetime
import functools
import json
import os
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
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português
sys.path.insert(0, str(RAIZ / "ferramentas"))

import dados_do_site  # noqa: E402
import janela  # noqa: E402
import nuvem  # noqa: E402
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
    IMAGENS_PERMITIDAS = {"img/janela.png", "img/janela.pt.png", "img/compartilhar.png", "favicon.svg"}

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


def jwt_falso(papel: str) -> str:
    """Só o formato de uma chave do Supabase (cabeçalho.dados.assinatura), sem valer nada."""
    parte = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f'{parte({"alg": "HS256", "typ": "JWT"})}.{parte({"iss": "supabase", "role": papel})}.assinatura-falsa'


class TestNuvem(unittest.TestCase):
    """Contas só pra salvar builds (Supabase): SQL com RLS só do dono, site que
    funciona sem config, só a chave pública e o supabase-js fixo com SRI."""

    SQL = (RAIZ / "ferramentas" / "supabase.sql").read_text(encoding="utf-8")
    JS = (RAIZ / "docs" / "nuvem.js").read_text(encoding="utf-8")
    HTML = (RAIZ / "docs" / "montar.html").read_text(encoding="utf-8")

    def csp(self, regra, html=None):
        csp = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', html or self.HTML).group(1)
        return next(p.strip() for p in csp.split(";") if p.strip().startswith(regra + " "))

    def test_sql_liga_rls_com_politicas_so_do_dono(self):
        sql = " ".join(self.SQL.split())
        self.assertIn("alter table public.builds enable row level security;", sql)
        self.assertIn("alter table public.builds force row level security;", sql)
        politicas = re.findall(r"create policy \"[^\"]+\" on public\.builds for (\w+) to authenticated ([^;]+);", sql)
        self.assertEqual(sorted(p[0] for p in politicas), ["delete", "insert", "select", "update"])
        for comando, regra in politicas:
            with self.subTest(comando):
                partes = re.findall(r"(?:using|with check) \((.+?)\)(?= with| *$)", regra)
                self.assertTrue(partes)
                for parte in partes:
                    self.assertEqual(parte, "(select auth.uid()) = user_id")
        self.assertRegex(sql, r"for update to authenticated using \(.+\) with check \(.+\)")
        self.assertIn("revoke all on public.builds from anon, public;", sql)

    def test_sql_guarda_o_minimo_com_limites(self):
        tabela = re.search(r"create table if not exists public\.builds \((.*?)\n\);", self.SQL, re.S).group(1)
        colunas = [linha.split()[0] for linha in tabela.splitlines() if re.match(r"^  [a-z_]+ ", linha)]
        self.assertEqual(colunas, ["id", "user_id", "nome", "classe", "dados", "criado", "alterado"])
        self.assertNotRegex(tabela.lower(), r"e-?mail|avatar|foto")
        self.assertIn("default auth.uid() references auth.users (id) on delete cascade", tabela)
        self.assertIn("octet_length(dados::text) <= 50000", tabela)
        self.assertIn(">= 50 then", self.SQL)
        # Os limites do site são os mesmos do banco.
        self.assertIn("const MAXIMO_DE_BUILDS = 50;", self.JS)
        self.assertIn("const MAXIMO_DA_BUILD = 50000;", self.JS)
        for classe in ler_json(DADOS / "jogo.json")["classes"]:
            self.assertIn(f"'{classe}'", tabela)

    def test_sql_apagar_conta_so_a_propria(self):
        funcao = re.search(r"create or replace function public\.apagar_minha_conta\(\).*?\$\$;", self.SQL, re.S).group(0)
        self.assertIn("security definer", funcao)
        self.assertIn("set search_path = ''", funcao)
        self.assertIn("delete from auth.users where id = auth.uid();", funcao)
        self.assertIn("revoke all on function public.apagar_minha_conta() from public, anon;", self.SQL)
        self.assertNotIn("service_role", self.SQL)

    def test_supabase_js_numa_versao_fixa_com_sri(self):
        url = re.search(r'const SUPABASE_JS = "([^"]+)";', self.JS).group(1)
        self.assertRegex(url, r"^https://cdn\.jsdelivr\.net/npm/@supabase/supabase-js@\d+\.\d+\.\d+/dist/umd/supabase\.js$")
        self.assertRegex(self.JS, r'const SUPABASE_SRI = "sha384-[A-Za-z0-9+/]{64}";')
        for linha in ("s.integrity = SUPABASE_SRI;", 's.crossOrigin = "anonymous";'):
            self.assertIn(linha, self.JS)
        # A CSP libera só esse arquivo (nem o resto do jsDelivr).
        self.assertEqual(self.csp("script-src"), f"script-src 'self' {url}")
        self.assertEqual(re.findall(r"https://[^\s\"'`]+", self.JS), [url])  # nenhum outro endereço fixo

    def test_connect_src_igual_ao_config(self):
        url, chave = nuvem.config_atual()
        self.assertEqual(self.csp("connect-src"), nuvem.connect_src(url))
        if url or chave:  # preenchido: tem que ser endereço do Supabase e chave pública
            self.assertEqual(nuvem.conferir(url, chave), (url, chave))

    def test_montador_carrega_a_nuvem_escondida(self):
        self.assertIn('<section class="nuvem" data-nuvem hidden></section>', self.HTML)
        ordem = [self.HTML.index(f'<script src="{js}"></script>') for js in ("idioma.js", "montar.js", "config-nuvem.js", "nuvem.js")]
        self.assertEqual(ordem, sorted(ordem))
        self.assertIn('href="nuvem.css"', self.HTML)
        montar = (RAIZ / "src" / "web" / "montar.js").read_text(encoding="utf-8")
        self.assertIn("paraNuvem, marcarNuvem, esquecerNuvem, daNuvem, nomeDaClasse,", montar)
        # Sem config, para logo no começo (antes de baixar qualquer coisa).
        ligar = self.JS[self.JS.index("async function ligar()"):]
        self.assertLess(ligar.index("if (!config)"), ligar.index("raiz.hidden = false"))
        self.assertLess(ligar.index("raiz.hidden = false"), ligar.index("lerSessao()"))

    def test_so_aceita_a_chave_publica(self):
        url = "https://abcdefghijklmnopqrst.supabase.co"
        self.assertEqual(nuvem.papel_da_chave(jwt_falso("anon")), "anon")
        self.assertEqual(nuvem.papel_da_chave("sb_publishable_abc123_XYZ"), "publishable")
        self.assertEqual(nuvem.papel_da_chave(jwt_falso("service_role")), "secreta")
        self.assertEqual(nuvem.papel_da_chave("sb_secret_abc123"), "secreta")
        self.assertEqual(nuvem.conferir(url + "/", " sb_publishable_abc "), (url, "sb_publishable_abc"))
        for chave in (jwt_falso("service_role"), "sb_secret_abc123", "nada", "a.b.c", ""):
            with self.subTest(chave[:20]), self.assertRaises(nuvem.ErroNuvem):
                nuvem.conferir(url, chave)
        for ruim in ("http://abc.supabase.co", "https://abc.supabase.co.mal.com", "https://mal.com", "https://abc.supabase.co/rest"):
            with self.subTest(ruim), self.assertRaises(nuvem.ErroNuvem):
                nuvem.conferir(ruim, jwt_falso("anon"))
        # O site confere do mesmo jeito (o JS também recusa service_role e sb_secret_).
        self.assertIn('dados.role === "anon"', self.JS)
        self.assertIn("sb_publishable_", self.JS)

    def test_ligar_e_desligar_mexe_so_no_config_e_na_csp(self):
        with tempfile.TemporaryDirectory() as pasta:
            docs = Path(pasta)
            for nome in ("config-nuvem.js", "montar.html"):
                (docs / nome).write_text((RAIZ / "docs" / nome).read_text(encoding="utf-8"), encoding="utf-8")
            antes = {n: (docs / n).read_text(encoding="utf-8") for n in ("config-nuvem.js", "montar.html")}
            nuvem.gravar("https://abcdefghijklmnopqrst.supabase.co", "sb_publishable_abc", docs)
            self.assertEqual(nuvem.config_atual(docs), ("https://abcdefghijklmnopqrst.supabase.co", "sb_publishable_abc"))
            html = (docs / "montar.html").read_text(encoding="utf-8")
            self.assertEqual(self.csp("connect-src", html), "connect-src 'self' https://abcdefghijklmnopqrst.supabase.co")
            self.assertEqual(self.csp("script-src", html), self.csp("script-src"))
            nuvem.gravar("", "", docs)
            if nuvem.config_atual() == ("", ""):
                for nome, texto in antes.items():
                    self.assertEqual((docs / nome).read_text(encoding="utf-8"), texto, nome)

    def test_nenhuma_chave_secreta_no_site(self):
        for arquivo in (RAIZ / "docs").rglob("*"):
            if arquivo.suffix not in {".js", ".html", ".json", ".txt", ".css"}:
                continue
            texto = arquivo.read_text(encoding="utf-8")
            with self.subTest(arquivo.name):
                self.assertNotRegex(texto, r"sb_secret_\w{6,}")
                for possivel in re.findall(r"eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+", texto):
                    self.assertNotEqual(nuvem.papel_da_chave(possivel), "secreta")


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
        for js in (RAIZ / "src" / "web" / "montar.js", RAIZ / "src" / "web" / "app.js", RAIZ / "docs" / "nuvem.js"):
            with self.subTest(js.name):
                faltam = sorted(self.frases_do_js(js) - set(self.en))
                self.assertEqual(faltam, [], "ponha em src/web/dados/en.json")

    @staticmethod
    def frases_do_python(caminho):
        """Os t("...") do Python (o ast junta as frases quebradas em várias linhas)."""
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        return {no.args[0].value for no in ast.walk(arvore)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "t"
                and no.args and isinstance(no.args[0], ast.Constant) and isinstance(no.args[0].value, str)}

    def test_toda_frase_do_python_tem_traducao(self):
        arquivos = [p for p in sorted((RAIZ / "src").glob("*.py")) if "from idioma import t" in p.read_text(encoding="utf-8")]
        self.assertGreaterEqual(len(arquivos), 8)
        for py in arquivos:
            with self.subTest(py.name):
                faltam = sorted(self.frases_do_python(py) - set(self.en))
                self.assertEqual(faltam, [], "ponha em src/web/dados/en.json")

    def test_selo_em_ingles(self):
        from nucleo import Avaliacao, montar_selo, texto_do_selo
        av = Avaliacao(item={"nome": "Fiendish Grips"}, resultados=[{
            "apelido": "Unhallowed", "bate": True, "por_enquanto": False, "item_da_build": True,
            "motivo": "Item da build: Fiendish Grips", "sobrando": ["+12% Life"],
            "afixos": [{"rotulo": "Destreza", "ok": True}, {"rotulo": "Dano crítico", "ok": False}]}])
        with mock.patch.dict("os.environ", {"D3C_IDIOMA": "en"}):
            texto = texto_do_selo(montar_selo(av))
        self.assertIn("✅ Unhallowed · build item", texto)
        self.assertIn("Has: " + self.en["Destreza"] + " ✓", texto)
        self.assertIn("Missing: " + self.en["Dano crítico"] + " ✗", texto)
        self.assertIn('Tip: at the Mystic, reroll "+12% Life" into ' + self.en["Dano crítico"] + ".", texto)
        self.assertIn("Tem: Destreza ✓", texto_do_selo(montar_selo(av)))  # e de volta em português

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
