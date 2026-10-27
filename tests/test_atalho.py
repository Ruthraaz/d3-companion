"""
Testes do atalho configurável (ATALHO no .env).

Rodar:
    python -m unittest discover tests
"""

import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português

from atalho import ler_atalho  # noqa: E402


class TestLerAtalho(unittest.TestCase):
    def test_tecla_simples(self):
        self.assertEqual(ler_atalho("F8"), (0, 0x77))
        self.assertEqual(ler_atalho("Insert"), (0, 0x2D))

    def test_com_modificadores_e_sem_diferenciar_maiusculas(self):
        self.assertEqual(ler_atalho("Ctrl+F8"), (0x0002, 0x77))
        self.assertEqual(ler_atalho("ctrl + shift + q"), (0x0002 | 0x0004, ord("Q")))

    def test_invalidos(self):
        for texto in ["", "F99", "Ctrl+", "Hyper+F8", "Ctrl+Banana"]:
            with self.subTest(texto):
                with self.assertRaises(ValueError):
                    ler_atalho(texto)


if __name__ == "__main__":
    unittest.main()
