"""
Testes de segurança: o que vem de fora (internet, arquivo de build, o que a
pessoa digita) não pode fazer o app abrir, gravar ou pedir o que não devia.

Rodar:
    python -m unittest discover tests
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português

from blizzard import Blizzard, ErroBlizzard  # noqa: E402
from config import ler_config, salvar_config  # noqa: E402
from heroi import conta_da_battletag  # noqa: E402
from nucleo import espaco_das_capturas, limpar_capturas  # noqa: E402
from maxroll import ErroMaxroll, baixar_planner, planners_do_link  # noqa: E402
from rede import RespostaGrande, ler, link_seguro  # noqa: E402


class TestLinkSeguro(unittest.TestCase):
    def test_link_do_maxroll(self):
        self.assertTrue(link_seguro("https://maxroll.gg/d3/guides/shadow-impale-demon-hunter-guide"))
        self.assertTrue(link_seguro("https://maxroll.gg/d3/planner/345357607"))

    def test_recusa_o_resto(self):
        for ruim in [
            "http://maxroll.gg/d3/guides/x",              # sem https
            "https://maxroll.gg.golpe.com/d3",             # outro site com o nome no começo
            "https://golpe.com/https://maxroll.gg/",       # maxroll só no caminho
            "https://usuario@maxroll.gg/",                 # usuário no endereço
            "https://maxroll.gg:8080/",                    # outra porta
            "file:///C:/Windows/System32/calc.exe",        # arquivo do PC
            "https://maxroll.gg/d3 & calc.exe",            # espaço (comando escondido)
            "https://maxroll.gg/d3\n",                     # quebra de linha
            "https://maxroll.gg/" + "a" * 600,             # longo demais
            None, 123,
        ]:
            self.assertFalse(link_seguro(ruim), ruim)


class TestTamanhoDaResposta(unittest.TestCase):
    def test_ate_o_limite_le(self):
        self.assertEqual(ler(io.BytesIO(b"x" * 10), maximo=10), b"x" * 10)

    def test_passou_do_limite_para(self):
        with self.assertRaises(RespostaGrande):
            ler(io.BytesIO(b"x" * 11), maximo=10)

    def test_maxroll_grande_demais_vira_erro_claro(self):
        import rede
        original, rede.MAXIMO = rede.MAXIMO, 32  # limite pequeno: não precisa gerar 20 MB
        try:
            with self.assertRaisesRegex(ErroMaxroll, "grande demais"):
                baixar_planner(1, lambda pedido, timeout=None: _Grande())
            with self.assertRaisesRegex(ErroMaxroll, "grande demais"):
                planners_do_link("https://maxroll.gg/d3/guides/x-guide", lambda pedido, timeout=None: _Grande())
        finally:
            rede.MAXIMO = original

    def test_blizzard_grande_demais_vira_erro_claro(self):
        api = Blizzard("id", "segredo", pasta_cache=Path(tempfile.mkdtemp()),
                       abrir=lambda pedido, timeout=None: _Grande())
        with self.assertRaisesRegex(ErroBlizzard, "grande demais"):
            api.pegar("/d3/data/hero/barbarian", guardar=False)


class _Grande(io.RawIOBase):
    """Resposta "infinita": nunca acaba de mandar bytes."""
    def readable(self):
        return True

    def readinto(self, b):
        b[:] = b"a" * len(b)
        return len(b)

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False


class TestBattleTag(unittest.TestCase):
    def test_nome_com_acento_vale(self):
        self.assertEqual(conta_da_battletag("Joãozinho#1234"), "Joãozinho-1234")

    def test_nao_deixa_mudar_o_endereco_da_api(self):
        for ruim in ("../../d3/data#1234", "a/b#1234", "nome?x=1#1234", "nome.x#1234", "a_b#1234"):
            with self.assertRaises(ErroBlizzard, msg=ruim):
                conta_da_battletag(ruim)


class TestEnv(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.env = Path(self.pasta.name) / ".env"
        self.env.write_text("BLIZZARD_CLIENT_ID=minha-chave\n", encoding="utf-8")

    def tearDown(self):
        self.pasta.cleanup()

    def test_quebra_de_linha_nao_cria_outra_chave(self):
        for chave, valor in [("BATTLETAG", "Jogador#1234\nBLIZZARD_CLIENT_ID=outra"),
                             ("ATALHO", "F8\nBLIZZARD_CLIENT_ID=outra"),
                             ("SELO_SEGUNDOS", "6\nBLIZZARD_CLIENT_ID=outra")]:
            self.assertIn(chave, salvar_config({chave: valor}, self.env), valor)
        self.assertEqual(self.env.read_text(encoding="utf-8"), "BLIZZARD_CLIENT_ID=minha-chave\n")

    def test_chave_desconhecida_nao_grava(self):
        erros = salvar_config({"BLIZZARD_CLIENT_ID": "outra"}, self.env)
        self.assertIn("BLIZZARD_CLIENT_ID", erros)
        self.assertEqual(self.env.read_text(encoding="utf-8"), "BLIZZARD_CLIENT_ID=minha-chave\n")
        self.assertNotIn("BLIZZARD_CLIENT_ID", ler_config(self.env))  # a janela nunca vê as chaves



class TestCapturas(unittest.TestCase):
    def test_guarda_so_as_mais_novas_e_nao_mexe_no_resto(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            nomes = ["20261024_100000.png", "20261024_110000_sem_dica.png", "20261025_090000.png"]
            for n in nomes + ["historico.jsonl", "minha_foto.png"]:
                (pasta / n).write_bytes(b"x")
            self.assertEqual(limpar_capturas(pasta, maximo=2), 1)
            self.assertEqual(sorted(p.name for p in pasta.iterdir()),
                             ["20261024_110000_sem_dica.png", "20261025_090000.png", "historico.jsonl", "minha_foto.png"])

    def test_tela_inteira_tem_limite_proprio(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            for h in range(5):
                (pasta / f"20261024_10000{h}_sem_dica.png").write_bytes(b"xx")
                (pasta / f"20261024_11000{h}.png").write_bytes(b"x")
            self.assertEqual(limpar_capturas(pasta, maximo=200, maximo_sem_dica=2), 3)
            self.assertEqual(sorted(p.name for p in pasta.glob("*sem_dica*")),
                             ["20261024_100003_sem_dica.png", "20261024_100004_sem_dica.png"])
            self.assertEqual(espaco_das_capturas(pasta), {"imagens": 7, "bytes": 9})
            self.assertEqual(limpar_capturas(pasta, maximo=0), 7)  # o botão "Apagar prints"
            self.assertEqual(espaco_das_capturas(pasta / "nao_existe"), {"imagens": 0, "bytes": 0})


class TestInstalador(unittest.TestCase):
    """O instalador não pede administrador, não troca de AppId (senão a versão
    nova não atualiza a velha) e não apaga os dados da pessoa ao desinstalar."""

    def setUp(self):
        self.iss = (RAIZ / "ferramentas" / "instalador.iss").read_text(encoding="utf-8")

    def test_por_usuario_e_appid_fixo(self):
        self.assertIn("PrivilegesRequired=lowest", self.iss)
        self.assertIn("AppId={{33F05C11-9D31-4E25-873E-D13D13F57021}", self.iss)

    def test_desinstalar_nao_mexe_nos_dados(self):
        apaga = self.iss.split("[UninstallDelete]")[1]
        self.assertNotIn("appdata", apaga.lower())  # só restos da pasta do app ({app})
        self.assertIn('Name: "{app}\\_internal"', apaga)

    def test_site_baixa_o_instalador(self):
        site = (RAIZ / "docs" / "site.js").read_text(encoding="utf-8")
        self.assertIn(r"/-Setup-[\d.]+\.exe$/i", site)


if __name__ == "__main__":
    unittest.main()
