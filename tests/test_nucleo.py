"""
Testes do núcleo (Etapa 5): o texto do selo e onde ele aparece.

O núcleo não depende de interface, então dá pra testar sem abrir janela.

Rodar:
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from avaliador import avaliar_todas, carregar_builds  # noqa: E402
from builds_dos_testes import BUILDS_DOS_TESTES  # noqa: E402
from nucleo import (Avaliacao, caixa_na_tela, montar_selo, posicao_do_selo,  # noqa: E402
                    texto_do_selo)
from parser import interpretar  # noqa: E402

# Só as 3 builds originais: builds importadas na pasta não podem mudar o resultado dos testes.
BUILDS = [b for b in carregar_builds() if b["id"] in BUILDS_DOS_TESTES]


def avaliacao(nome: str) -> Avaliacao:
    texto = (RAIZ / "tests" / "ocr_recorte" / f"{nome}.txt").read_text(encoding="utf-8")
    item = interpretar(texto)
    return Avaliacao(item=item, resultados=avaliar_todas(item, BUILDS))


class TestSelo(unittest.TestCase):
    def test_serve_mostra_build_e_afixos(self):
        selo = montar_selo(avaliacao("set_fiendish_grips"))
        self.assertTrue(selo.serve)
        self.assertEqual(texto_do_selo(selo),
                         "Fiendish Grips\n"
                         "✅ Unhallowed · Destreza ✓  Vitalidade ✓  Crítico ✓  Dano crítico ✗")

    def test_varias_builds_uma_linha_cada(self):
        selo = montar_selo(avaliacao("lendario_demon_machine"))
        linhas = texto_do_selo(selo).splitlines()
        self.assertEqual(linhas[1], "✅ Dreadlands · Destreza ✓  Vitalidade ✓  Dano da arma ✓  Encaixe ✗")
        # LoN não bate (precisa ser Ancient) e a Unhallowed pede Yang's Recurve
        # (arma do guia do Maxroll).
        self.assertEqual(len(linhas), 2)

    def test_nao_serve_mostra_o_motivo(self):
        selo = montar_selo(avaliacao("lendario_cloak_garwulf"))
        self.assertFalse(selo.serve)
        self.assertEqual(texto_do_selo(selo).splitlines()[1:],
                         ["❌ Não serve", "Dreadlands: A build pede: Galvanized Vest"])

    def test_gema(self):
        selo = montar_selo(avaliacao("gema_zei"))
        self.assertTrue(selo.serve)
        self.assertIn("✅ Dreadlands · Gema da build", texto_do_selo(selo))

    def test_raro_sem_nome_usa_qualidade_e_tipo(self):
        selo = montar_selo(avaliacao("raro_vampiric_source_equipado"))
        self.assertEqual(selo.titulo, "Rare Ring")

    def test_erro(self):
        selo = montar_selo(Avaliacao(erro="Não achei a dica perto do mouse."))
        self.assertFalse(selo.serve)
        self.assertIn("Não achei a dica", texto_do_selo(selo))


class TestPosicao(unittest.TestCase):
    TELA = (0, 0, 1920, 1080)

    def test_caixa_na_tela_desconta_a_folga_do_titulo(self):
        # Print começando em (300, 0); recorte em (10, 30)-(410, 700) com folga de 70 em cima.
        av = Avaliacao(caixa=(10, 30, 410, 700))
        self.assertEqual(caixa_na_tela(av, (300, 0), (0, 0)), (310, 100, 710, 700))

    def test_caixa_na_tela_usa_o_grupo_com_a_dica_do_equipado(self):
        # Dica do item em x 10-410 e a do equipado colada até x 820.
        av = Avaliacao(caixa=(10, 30, 410, 700), grupo=(10, 820))
        self.assertEqual(caixa_na_tela(av, (300, 0), (0, 0)), (310, 100, 1120, 700))

    def test_caixa_na_tela_sem_dica_usa_o_mouse(self):
        self.assertEqual(caixa_na_tela(Avaliacao(), (300, 0), (50, 60)), (350, 60, 351, 61))

    def test_a_direita_da_dica(self):
        self.assertEqual(posicao_do_selo((500, 200, 900, 800), (300, 80), self.TELA), (908, 200))

    def test_sem_espaco_a_direita_vai_pra_esquerda(self):
        self.assertEqual(posicao_do_selo((1500, 200, 1900, 800), (300, 80), self.TELA), (1192, 200))

    def test_nunca_sai_da_tela(self):
        x, y = posicao_do_selo((100, 1050, 1800, 1079), (300, 80), self.TELA)
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(y + 80, 1080)

    def test_segundo_monitor(self):
        tela = (1920, 0, 3840, 1080)
        self.assertEqual(posicao_do_selo((2000, 100, 2400, 600), (300, 80), tela), (2408, 100))


if __name__ == "__main__":
    unittest.main()
