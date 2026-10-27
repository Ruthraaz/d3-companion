"""
Testes da atualização (src/atualizar.py): sem internet, um "GitHub de mentira"
responde no formato da API de Releases.

Rodar:
    python -m unittest discover tests
"""

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português

import atualizar  # noqa: E402
from atualizar import ErroAtualizacao, baixar, comando_de_instalar, numero, versao_nova  # noqa: E402

CONTEUDO = b"instalador de mentira" * 1000
BASE = "https://github.com/Ruthraaz/d3-companion/releases/download/"


def release(tag="v1.0.9", **mudar_instalador):
    instalador = {"name": "D3-Companion-Setup-1.0.9.exe", "size": len(CONTEUDO),
                  "browser_download_url": BASE + "v1.0.9/D3-Companion-Setup-1.0.9.exe",
                  "digest": "sha256:" + hashlib.sha256(CONTEUDO).hexdigest()} | mudar_instalador
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
        {"name": "D3-Companion-1.0.9-windows.zip", "size": 10, "browser_download_url": BASE + "v1.0.9/x.zip"},
        instalador]}


def github(resposta):
    def abrir(pedido, timeout=None):
        if isinstance(resposta, Exception):
            raise resposta
        return io.BytesIO(json.dumps(resposta).encode())
    return abrir


class TestVersaoNova(unittest.TestCase):
    def test_numero(self):
        self.assertEqual(numero("v1.0.10"), (1, 0, 10))
        self.assertGreater(numero("1.0.10"), numero("1.0.9"))  # 10 > 9, não "1" < "9"
        self.assertIsNone(numero("v1.0"))
        self.assertIsNone(numero("1.0.3; rm -rf"))

    def test_tem_versao_nova(self):
        nova = versao_nova(github(release()), atual="1.0.3")
        self.assertEqual(nova["versao"], "1.0.9")
        self.assertEqual(nova["instalador"]["nome"], "D3-Companion-Setup-1.0.9.exe")
        self.assertEqual(nova["instalador"]["sha256"], hashlib.sha256(CONTEUDO).hexdigest())

    def test_mesma_ou_mais_velha_nao_avisa(self):
        self.assertIsNone(versao_nova(github(release("v1.0.3")), atual="1.0.3"))
        self.assertIsNone(versao_nova(github(release("v1.0.2")), atual="1.0.3"))

    def test_rascunho_e_beta_nao_avisam(self):
        self.assertIsNone(versao_nova(github(release() | {"draft": True}), atual="1.0.3"))
        self.assertIsNone(versao_nova(github(release() | {"prerelease": True}), atual="1.0.3"))

    def test_sem_internet_ou_resposta_estranha_fica_quieto(self):
        self.assertIsNone(versao_nova(github(urllib.error.URLError("sem rede")), atual="1.0.3"))
        self.assertIsNone(versao_nova(github({"mensagem": "rate limit"}), atual="1.0.3"))
        self.assertIsNone(versao_nova(github(release("lixo")), atual="1.0.3"))

    def test_instalador_de_outro_lugar_nao_vale(self):
        for ruim in ({"browser_download_url": "https://golpe.com/D3-Companion-Setup-1.0.9.exe"},
                     {"browser_download_url": BASE + "v1.0.8/D3-Companion-Setup-1.0.9.exe"},
                     {"name": "D3-Companion-Setup-1.0.9.exe.bat"},
                     {"digest": None},
                     {"size": 10**10}):
            nova = versao_nova(github(release(**ruim)), atual="1.0.3")
            self.assertIsNone(nova["instalador"], ruim)  # avisa, mas não instala sozinho


class TestBaixar(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.instalador = versao_nova(github(release()), atual="1.0.3")["instalador"]

    def test_baixa_e_confere(self):
        (self.pasta / "D3-Companion-Setup-1.0.5.exe").write_bytes(b"velho")
        partes = []
        arquivo = baixar(self.instalador, self.pasta, abrir=lambda p, timeout=None: io.BytesIO(CONTEUDO),
                         progresso=partes.append)
        self.assertEqual(arquivo.read_bytes(), CONTEUDO)
        self.assertEqual(partes[-1], 1.0)
        self.assertEqual([p.name for p in self.pasta.iterdir()], [arquivo.name])  # o velho saiu

    def test_arquivo_diferente_nao_fica(self):
        for errado in (CONTEUDO[:-1] + b"X", CONTEUDO[:100], CONTEUDO + b"a mais"):
            with self.assertRaisesRegex(ErroAtualizacao, "diferente"):
                baixar(self.instalador, self.pasta, abrir=lambda p, timeout=None, e=errado: io.BytesIO(e))
            self.assertEqual(list(self.pasta.iterdir()), [])

    def test_endereco_de_fora_nem_baixa(self):
        with self.assertRaisesRegex(ErroAtualizacao, "estranho"):
            baixar(self.instalador | {"url": "https://golpe.com/x.exe"}, self.pasta,
                   abrir=lambda p, timeout=None: self.fail("não era pra baixar"))

    def test_sem_internet(self):
        def sem_rede(pedido, timeout=None):
            raise urllib.error.URLError("sem rede")
        with self.assertRaisesRegex(ErroAtualizacao, "internet"):
            baixar(self.instalador, self.pasta, abrir=sem_rede)


class TestInstalar(unittest.TestCase):
    def test_espera_o_app_fechar_e_instala_sem_perguntas(self):
        arquivo = Path(r"C:\Users\Fulano de Tal\AppData\Local\Temp\D3-Companion-Setup-1.0.9.exe")
        comando = comando_de_instalar(arquivo)
        self.assertTrue(comando.startswith("cmd /c ping -n 4 127.0.0.1 >nul & "))
        self.assertIn(f'"{arquivo}" /SILENT', comando)  # aspas: pasta com espaço

    def test_do_codigo_nao_instala_sozinho(self):
        self.assertFalse(atualizar.instalado())  # os testes rodam do código, não do .exe

    def test_instalador_abre_o_app_de_novo(self):
        iss = (RAIZ / "ferramentas" / "instalador.iss").read_text(encoding="utf-8")
        self.assertIn("Flags: nowait; Check: WizardSilent", iss)


if __name__ == "__main__":
    unittest.main()
