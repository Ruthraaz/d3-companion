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
from avaliador import (ESPACOS, avaliar_todas, builds_escolhidas, carregar_builds,  # noqa: E402
                       ficha_da_build)
from builds_dos_testes import BUILDS_DOS_TESTES  # noqa: E402
from config import ler_config, salvar_config  # noqa: E402
from nucleo import Avaliacao, Selo, montar_selo, texto_do_selo  # noqa: E402


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
        self.assertEqual(ler_config(self.env), {"ATALHO": "F8", "SELO_SEGUNDOS": "6", "BUILD_ATIVA": "", "AUTOMATICO": "sim", "BATTLETAG": ""})

    def test_salva_sem_mexer_no_resto(self):
        self.env.write_text("# meu comentário\nTESSERACT_CMD=C:\\Tess\\tesseract.exe\nATALHO=F8\n",
                            encoding="utf-8")
        self.assertEqual(salvar_config({"ATALHO": "Ctrl+F9", "SELO_SEGUNDOS": "4,5"}, self.env), {})
        texto = self.env.read_text(encoding="utf-8")
        self.assertIn("# meu comentário", texto)
        self.assertIn("TESSERACT_CMD=C:\\Tess\\tesseract.exe", texto)
        self.assertEqual(ler_config(self.env), {"ATALHO": "Ctrl+F9", "SELO_SEGUNDOS": "4.5", "BUILD_ATIVA": "", "AUTOMATICO": "sim", "BATTLETAG": ""})

    def test_invalido_nao_grava_nada(self):
        self.env.write_text("ATALHO=F8\n", encoding="utf-8")
        erros = salvar_config({"ATALHO": "Ctrl+Banana", "SELO_SEGUNDOS": "90"}, self.env)
        self.assertEqual(set(erros), {"ATALHO", "SELO_SEGUNDOS"})
        self.assertEqual(self.env.read_text(encoding="utf-8"), "ATALHO=F8\n")


class TestBuildEscolhida(unittest.TestCase):
    """Na janela, clicar numa build faz o atalho avaliar só com ela."""

    def setUp(self):
        self.builds = [b for b in carregar_builds() if b["id"] in BUILDS_DOS_TESTES]  # só as originais
        self.pasta = tempfile.TemporaryDirectory()
        self.env = Path(self.pasta.name) / ".env"

    def tearDown(self):
        self.pasta.cleanup()

    def test_id_e_o_nome_do_arquivo(self):
        self.assertIn("legacy_of_nightmares", {b["id"] for b in self.builds})

    def test_escolhida_vazia_ou_que_sumiu_usa_todas(self):
        self.assertEqual(builds_escolhidas(self.builds, ""), self.builds)
        self.assertEqual(builds_escolhidas(self.builds, "build_apagada"), self.builds)

    def test_so_a_escolhida(self):
        usadas = builds_escolhidas(self.builds, "legacy_of_nightmares")
        self.assertEqual([b["apelido"] for b in usadas], ["LoN"])

    def test_gema_fora_da_lon_mostra_o_motivo_da_lon(self):
        # O caso do Arthur: com LoN escolhida, o selo não pode falar da Dreadlands.
        gema = {"nome": "Gem of Ease", "qualidade": "Legendary", "tipo": "Gem"}
        usadas = builds_escolhidas(self.builds, "legacy_of_nightmares")
        selo = montar_selo(Avaliacao(item=gema, resultados=avaliar_todas(gema, usadas)))
        self.assertIn("LoN: Gema fora da build", texto_do_selo(selo))
        self.assertNotIn("Dreadlands", texto_do_selo(selo))

    def test_config_aceita_build_que_existe_e_vazio(self):
        self.assertEqual(salvar_config({"BUILD_ATIVA": "legacy_of_nightmares"}, self.env), {})
        self.assertEqual(ler_config(self.env)["BUILD_ATIVA"], "legacy_of_nightmares")
        self.assertEqual(salvar_config({"BUILD_ATIVA": ""}, self.env), {})
        self.assertEqual(ler_config(self.env)["BUILD_ATIVA"], "")

    def test_config_automatico_liga_e_desliga(self):
        self.assertEqual(salvar_config({"AUTOMATICO": "nao"}, self.env), {})
        self.assertEqual(ler_config(self.env)["AUTOMATICO"], "nao")
        self.assertIn("AUTOMATICO", salvar_config({"AUTOMATICO": "talvez"}, self.env))

    def test_config_recusa_build_que_nao_existe(self):
        self.assertIn("BUILD_ATIVA", salvar_config({"BUILD_ATIVA": "inventada"}, self.env))

    def test_historico_guarda_com_qual_build(self):
        arquivo = Path(self.pasta.name) / "historico.jsonl"
        historico.registrar(Avaliacao(), Selo(False, "X", []), arquivo, com="LoN")
        self.assertEqual(historico.ler(1, arquivo)[0]["com"], "LoN")


class TestFichaDaBuild(unittest.TestCase):
    def setUp(self):
        self.builds = {b["apelido"]: b for b in carregar_builds() if b["id"] in BUILDS_DOS_TESTES}

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
