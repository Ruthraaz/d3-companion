"""
Testes da avaliação automática (passar o mouse no item):

  - TestVigia: as decisões do vigia (quando avaliar, reaproveitar, esconder),
    só com assinaturas inventadas — não precisa de tela nem de jogo.
  - TestOlhadaRapida: a olhada barata acha a dica nos prints de samples/ e
    não vê dica onde não tem.

Rodar:
    python -m unittest discover tests
"""

import os
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português

import vigia as vigia_mod  # noqa: E402
from captura import achar_dica, olhada_rapida  # noqa: E402
from vigia import AVALIAR, ESCONDER, GUARDADO, NADA, Vigia  # noqa: E402


class TestVigia(unittest.TestCase):
    def setUp(self):
        self.v = Vigia()

    def test_espera_a_dica_parar_antes_de_avaliar(self):
        self.assertEqual(self.v.olhar("a")[0], NADA)      # acabou de aparecer
        self.assertEqual(self.v.olhar("a")[0], AVALIAR)   # repetiu: parada
        self.assertEqual(self.v.olhar("a")[0], NADA)      # já avaliada, selo na tela

    def test_dica_ainda_mudando_nao_avalia(self):
        for assinatura in ("a", "b", "c", "d"):
            self.assertEqual(self.v.olhar(assinatura)[0], NADA)

    def test_esconde_depois_de_duas_olhadas_sem_dica(self):
        self.v.olhar("a"), self.v.olhar("a")
        self.assertEqual(self.v.olhar(None)[0], NADA)  # uma olhada sem dica pode ser piscada
        self.assertEqual(self.v.olhar(None)[0], ESCONDER)
        self.assertEqual(self.v.olhar(None)[0], NADA)  # não manda esconder de novo

    def test_sem_selo_na_tela_nao_manda_esconder(self):
        self.assertEqual(self.v.olhar(None)[0], NADA)
        self.assertEqual(self.v.olhar(None)[0], NADA)

    def test_volta_no_mesmo_item_usa_o_guardado(self):
        self.v.olhar("a"), self.v.olhar("a")
        self.v.guardar("a", "selo do a")
        self.v.olhar(None), self.v.olhar(None)
        self.v.olhar("a")
        self.assertEqual(self.v.olhar("a"), (GUARDADO, "selo do a"))

    def test_o_que_nao_era_item_fica_quieto(self):
        self.v.olhar("menu"), self.v.olhar("menu")
        self.v.guardar("menu", None)
        self.v.olhar(None), self.v.olhar(None)
        self.v.olhar("menu")
        self.assertEqual(self.v.olhar("menu")[0], NADA)

    def test_trocar_direto_de_item(self):
        self.v.olhar("a"), self.v.olhar("a")
        self.v.olhar("b")
        self.assertEqual(self.v.olhar("b")[0], AVALIAR)

    def test_esquecer_tela(self):
        self.assertFalse(self.v.esquecer_tela())
        self.v.olhar("a"), self.v.olhar("a")
        self.v.guardar("a", "selo do a")
        self.assertTrue(self.v.esquecer_tela())
        # Voltando pro jogo com a mesma dica: mostra de novo, sem OCR.
        self.v.olhar("a")
        self.assertEqual(self.v.olhar("a"), (GUARDADO, "selo do a"))

    def test_guarda_no_maximo(self):
        for i in range(vigia_mod.GUARDAR_NO_MAXIMO + 5):
            self.v.guardar(i, f"selo {i}")
        self.v.olhar(0)
        self.assertEqual(self.v.olhar(0)[0], AVALIAR)  # o mais velho saiu


def print_e_mouse_na_dica(nome: str):
    """Abre um print de samples/ e põe o "mouse" no meio da dica."""
    img = Image.open(RAIZ / "samples" / nome).convert("RGB")
    x0, y0, x1, y1 = achar_dica(np.asarray(img)[:, :, ::-1].copy())  # achar_dica usa BGR
    return img, ((x0 + x1) // 2, (y0 + y1) // 2)


class TestOlhadaRapida(unittest.TestCase):
    def test_acha_a_dica_nos_prints(self):
        for p in sorted((RAIZ / "samples").glob("*.png")):
            with self.subTest(p.name):
                img, cursor = print_e_mouse_na_dica(p.name)
                self.assertIsNotNone(olhada_rapida(img, cursor))

    def test_mesma_tela_mesma_assinatura(self):
        img, cursor = print_e_mouse_na_dica("gema_zei.png")
        self.assertEqual(olhada_rapida(img, cursor), olhada_rapida(img.copy(), cursor))

    def test_itens_diferentes_assinaturas_diferentes(self):
        assinaturas = set()
        for nome in ("gema_zei", "gema_pain_enhancer", "set_fiendish_grips"):
            assinaturas.add(olhada_rapida(*print_e_mouse_na_dica(f"{nome}.png")))
        self.assertEqual(len(assinaturas), 3)

    def test_tela_sem_dica(self):
        cinza = Image.new("RGB", (1200, 900), (90, 80, 70))
        self.assertIsNone(olhada_rapida(cinza, (600, 450)))

    def test_dica_longe_do_mouse_nao_conta(self):
        img, _ = print_e_mouse_na_dica("gema_zei.png")
        grande = Image.new("RGB", (img.width + 2000, img.height), (90, 80, 70))
        grande.paste(img, (0, 0))
        self.assertIsNone(olhada_rapida(grande, (grande.width - 10, img.height // 2)))


if __name__ == "__main__":
    unittest.main()
