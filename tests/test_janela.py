"""
Testes do que a janela principal usa (sem abrir janela nenhuma):
histórico em arquivo, configurações no .env e a ficha da build.

Rodar:
    python -m unittest discover tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import historico  # noqa: E402
from avaliador import ESPACOS, carregar_builds, ficha_da_build  # noqa: E402
from config import ler_config, salvar_config  # noqa: E402
from nucleo import Avaliacao, Selo  # noqa: E402


class TestHistorico(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.arquivo = Path(self.pasta.name) / "historico.jsonl"

    def tearDown(self):
        self.pasta.cleanup()

    def test_grava_e_le_do_mais_novo_pro_mais_antigo(self):
        for nome in ["Primeiro", "Segundo", "Terceiro"]:
            selo = Selo(True, nome, [[("✅ ", "normal"), ("Dreadlands", "build")]])
            historico.registrar(Avaliacao(item={"qualidade": "Set"}), selo, self.arquivo)
        lidos = historico.ler(2, self.arquivo)
        self.assertEqual([h["titulo"] for h in lidos], ["Terceiro", "Segundo"])
        self.assertEqual(lidos[0]["linhas"], [[["✅ ", "normal"], ["Dreadlands", "build"]]])
        self.assertTrue(lidos[0]["serve"])

    def test_linha_estragada_nao_estraga_o_resto(self):
        historico.registrar(Avaliacao(), Selo(False, "Bom", []), self.arquivo)
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write('{"titulo": "cortad')  # app fechado no meio da escrita
        self.assertEqual([h["titulo"] for h in historico.ler(10, self.arquivo)], ["Bom"])

    def test_sem_arquivo(self):
        self.assertEqual(historico.ler(10, self.arquivo), [])


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.env = Path(self.pasta.name) / ".env"

    def tearDown(self):
        self.pasta.cleanup()

    def test_padroes_sem_env(self):
        self.assertEqual(ler_config(self.env), {"ATALHO": "F8", "SELO_SEGUNDOS": "6"})

    def test_salva_sem_mexer_no_resto(self):
        self.env.write_text("# meu comentário\nTESSERACT_CMD=C:\\Tess\\tesseract.exe\nATALHO=F8\n",
                            encoding="utf-8")
        self.assertEqual(salvar_config({"ATALHO": "Ctrl+F9", "SELO_SEGUNDOS": "4,5"}, self.env), {})
        texto = self.env.read_text(encoding="utf-8")
        self.assertIn("# meu comentário", texto)
        self.assertIn("TESSERACT_CMD=C:\\Tess\\tesseract.exe", texto)
        self.assertEqual(ler_config(self.env), {"ATALHO": "Ctrl+F9", "SELO_SEGUNDOS": "4.5"})

    def test_invalido_nao_grava_nada(self):
        self.env.write_text("ATALHO=F8\n", encoding="utf-8")
        erros = salvar_config({"ATALHO": "Ctrl+Banana", "SELO_SEGUNDOS": "90"}, self.env)
        self.assertEqual(set(erros), {"ATALHO", "SELO_SEGUNDOS"})
        self.assertEqual(self.env.read_text(encoding="utf-8"), "ATALHO=F8\n")


class TestFichaDaBuild(unittest.TestCase):
    def setUp(self):
        self.builds = {b["apelido"]: b for b in carregar_builds()}

    def test_soma_as_regras_gerais_em_cada_espaco(self):
        ficha = ficha_da_build(self.builds["Dreadlands"])
        cabeca = ficha["espacos"]["Head"]
        self.assertEqual(cabeca["itens"], ["Dystopian Goggles"])
        self.assertEqual(cabeca["obrigatorios"], ["Destreza"])
        self.assertEqual(cabeca["desejaveis"], ["Vitalidade", "Encaixe", "Crítico"])

    def test_espaco_fora_do_json_vale_so_as_regras_gerais(self):
        # Dreadlands não fala de cintura: o avaliador ainda pede Destreza lá.
        ficha = ficha_da_build(self.builds["Dreadlands"])
        self.assertEqual(set(ficha["espacos"]), set(ESPACOS))
        cintura = ficha["espacos"]["Waist"]
        self.assertFalse(cintura["definido"])
        self.assertEqual(cintura["obrigatorios"], ["Destreza"])

    def test_ancient_do_espaco_vence_o_da_build(self):
        ficha = ficha_da_build(self.builds["LoN"])
        self.assertTrue(ficha["espacos"]["Head"]["exige_ancient"])
        self.assertFalse(ficha["espacos"]["Finger"]["exige_ancient"])


if __name__ == "__main__":
    unittest.main()
