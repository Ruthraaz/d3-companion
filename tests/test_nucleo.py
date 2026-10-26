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
                    processo_vivo, texto_do_selo)
from parser import interpretar  # noqa: E402

# Só as 3 builds originais: builds importadas na pasta não podem mudar o resultado dos testes.
BUILDS = [b for b in carregar_builds() if b["id"] in BUILDS_DOS_TESTES]


def avaliacao(nome: str) -> Avaliacao:
    texto = (RAIZ / "tests" / "ocr_recorte" / f"{nome}.txt").read_text(encoding="utf-8")
    item = interpretar(texto)
    return Avaliacao(item=item, resultados=avaliar_todas(item, BUILDS))


class TestSelo(unittest.TestCase):
    def test_item_da_build_diz_o_que_tem_o_que_falta_e_o_que_trocar(self):
        selo = montar_selo(avaliacao("set_fiendish_grips"))
        self.assertTrue(selo.serve)
        self.assertEqual(texto_do_selo(selo).splitlines(), [
            "Fiendish Grips",
            "✅ Unhallowed · item da build",
            "Tem: Destreza ✓  Vitalidade ✓  Crítico ✓",
            "Falta: Dano crítico ✗",
            # Velocidade de ataque não está nas regras das luvas: é essa que vale trocar.
            'Dica: no Místico, troque "Attack Speed Increased by 5.0%" por Dano crítico.',
        ])

    def test_espaco_sem_item_definido(self):
        selo = montar_selo(avaliacao("lendario_demon_machine"))
        linhas = texto_do_selo(selo).splitlines()
        self.assertEqual(linhas[1:3], ["✅ Dreadlands · serve neste espaço",
                                       "Tem: Destreza ✓  Vitalidade ✓  Dano da arma ✓"])
        # LoN não bate (precisa ser Ancient) e a Unhallowed pede Yang's Recurve:
        # só a Dreadlands aparece.
        self.assertNotIn("LoN", texto_do_selo(selo))

    def test_tudo_certo_sem_dica(self):
        selo = montar_selo(avaliacao("set_antique_vintage_boots"))
        self.assertEqual(texto_do_selo(selo).splitlines()[1:],
                         ["✅ Dreadlands · item da build · tudo certo", "Tem: Destreza ✓  Vitalidade ✓"])

    def test_varias_builds_as_outras_em_uma_linha(self):
        selo = montar_selo(avaliacao("set_litany_of_the_undaunted"))
        self.assertEqual(texto_do_selo(selo).splitlines()[-1], "✅ LoN · 2 de 5 afixos")

    def test_item_errado_com_os_afixos_serve_por_enquanto(self):
        # Pra upar: o Cloak não é o peito da build, mas tem Destreza e encaixe.
        selo = montar_selo(avaliacao("lendario_cloak_garwulf"))
        self.assertFalse(selo.serve)
        self.assertTrue(selo.parcial)
        self.assertEqual(texto_do_selo(selo).splitlines()[1:4],
                         ["🟡 Por enquanto · Dreadlands · A build pede: Galvanized Vest",
                          "Tem: Destreza ✓  Encaixe ✓",
                          "Falta: Vitalidade ✗"])

    def test_nao_serve_mostra_o_motivo(self):
        # Sem Destreza (obrigatória) não serve nem por enquanto.
        item = interpretar((RAIZ / "tests" / "ocr_recorte" / "lendario_cloak_garwulf.txt")
                           .read_text(encoding="utf-8"))
        item["primarios"] = [a for a in item["primarios"] if "Dexterity" not in a["modelo"]]
        selo = montar_selo(Avaliacao(item=item, resultados=avaliar_todas(item, BUILDS)))
        self.assertFalse(selo.serve or selo.parcial)
        self.assertEqual(texto_do_selo(selo).splitlines()[1:],
                         ["❌ Não serve", "Dreadlands: A build pede: Galvanized Vest"])

    def test_poucos_desejaveis_nao_serve_por_enquanto(self):
        # Item errado com menos da metade dos desejáveis: continua "não serve".
        item = interpretar((RAIZ / "tests" / "ocr_recorte" / "lendario_cloak_garwulf.txt")
                           .read_text(encoding="utf-8"))
        item["soquetes"] = 0  # sobra só Destreza (Vitalidade e Encaixe faltam)
        dread = [b for b in BUILDS if b["apelido"] == "Dreadlands"]
        selo = montar_selo(Avaliacao(item=item, resultados=avaliar_todas(item, dread)))
        self.assertFalse(selo.parcial)

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


class TestProcessoVivo(unittest.TestCase):
    """O overlay usa isso pra fechar junto com a janela."""

    def test_vivo_e_morto(self):
        import os
        import subprocess
        self.assertTrue(processo_vivo(os.getpid()))
        filho = subprocess.Popen([sys.executable, "-c", "pass"])
        filho.wait()
        self.assertFalse(processo_vivo(filho.pid))


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
