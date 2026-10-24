"""
Testes da Etapa 7: uma classe nova entra só com um JSON, e JSON errado avisa
em vez de derrubar o app ou sumir com regra calado.

Rodar:
    python -m unittest discover tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from avaliador import avaliar, ler_builds, problemas_da_build  # noqa: E402

EXEMPLOS = RAIZ / "builds" / "exemplos"


def build_minima(**mudancas) -> dict:
    return {"formato": 1, "nome": "Teste", "classe": "Demon Hunter"} | mudancas


class TestBuildsDoProjeto(unittest.TestCase):
    def test_todas_as_builds_estao_ok(self):
        _, problemas = ler_builds()
        self.assertEqual(problemas, {})

    def test_modelo_de_outra_classe_esta_ok(self):
        builds, problemas = ler_builds(EXEMPLOS)
        self.assertEqual(problemas, {})
        self.assertIn("Barbarian", {b["classe"] for b in builds})


class TestOutraClasse(unittest.TestCase):
    """Nada de Demon Hunter fixo no código: o modelo de Bárbaro funciona igual."""

    def setUp(self):
        self.barbaro = next(b for b in ler_builds(EXEMPLOS)[0] if b["classe"] == "Barbarian")

    def item(self, afixos, classe=None):
        return {"nome": "Luvas", "qualidade": "Legendary", "tipo": "Gloves", "slot": "Hands",
                "classe": classe, "soquetes": 0,
                "primarios": [{"texto": t, "modelo": m, "valores": v} for t, m, v in afixos],
                "secundarios": []}

    def test_forca_serve_e_destreza_nao(self):
        forca = self.item([("+700 Strength", "+# Strength", [700])])
        destreza = self.item([("+700 Dexterity", "+# Dexterity", [700])])
        self.assertTrue(avaliar(forca, self.barbaro)["bate"])
        r = avaliar(destreza, self.barbaro)
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "Falta: Força")

    def test_item_de_demon_hunter_nao_serve_pro_barbaro(self):
        item = self.item([("+700 Strength", "+# Strength", [700])], classe="Demon Hunter")
        self.assertEqual(avaliar(item, self.barbaro)["motivo"], "Item de Demon Hunter")

    def test_minimo_conta(self):
        # O modelo pede Dano crítico com mínimo 40 nas mãos.
        pouco = self.item([("+700 Strength", "+# Strength", [700]),
                           ("Critical Hit Damage Increased by 30%", "Critical Hit Damage Increased by #%", [30])])
        r = avaliar(pouco, self.barbaro)
        self.assertIn("Dano crítico (mín. 40)", r["desejaveis"]["faltando"])


class TestConferencia(unittest.TestCase):
    def test_build_ok_nao_tem_problema(self):
        self.assertEqual(problemas_da_build(build_minima()), [])

    def test_espaco_com_erro_de_digitacao_sugere_o_certo(self):
        [problema] = problemas_da_build(build_minima(espacos={"Hand": {"itens": []}}))
        self.assertIn("'Hand' não existe", problema)
        self.assertIn("Quis dizer 'Hands'?", problema)

    def test_chave_com_erro_de_digitacao(self):
        [problema] = problemas_da_build(build_minima(espacos={"Hands": {"desejavel": []}}))
        self.assertIn("'desejavel' não existe", problema)
        self.assertIn("'desejaveis'", problema)

    def test_classe_errada(self):
        [problema] = problemas_da_build(build_minima(classe="Demon Hunte"))
        self.assertIn("Quis dizer 'Demon Hunter'?", problema)

    def test_regras_e_listas_no_formato_errado(self):
        problemas = problemas_da_build(build_minima(
            todos_os_espacos={"obrigatorios": "+# Dexterity"},
            espacos={"Head": {"itens": "Dystopian Goggles",
                              "desejaveis": [{"rotulo": "sem modelo"}, {"modelo": "x", "minimo": "40"}]}},
            gemas="Zei"))
        self.assertEqual(len(problemas), 5)

    def test_comentario_com_sublinhado_e_permitido(self):
        self.assertEqual(problemas_da_build(build_minima(_nota="qualquer coisa")), [])

    def test_formato_nome_e_objeto(self):
        self.assertEqual(len(problemas_da_build({"classe": "Monk"})), 2)  # formato e nome
        self.assertEqual(problemas_da_build([]), ["O arquivo precisa ser um objeto JSON { ... }."])


class TestBuildComErroFicaDeFora(unittest.TestCase):
    def test_json_quebrado_nao_derruba_as_outras(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            (pasta / "boa.json").write_text(json.dumps(build_minima()), encoding="utf-8")
            (pasta / "quebrada.json").write_text('{"formato": 1, "nome": "x",}', encoding="utf-8")
            (pasta / "errada.json").write_text(json.dumps(build_minima(classe="Paladino")), encoding="utf-8")
            builds, problemas = ler_builds(pasta)
        self.assertEqual([b["id"] for b in builds], ["boa"])
        self.assertEqual(set(problemas), {"quebrada.json", "errada.json"})
        self.assertIn("linha 1", problemas["quebrada.json"][0])


if __name__ == "__main__":
    unittest.main()
