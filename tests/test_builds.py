"""
Testes da Etapa 7: uma classe nova entra só com um JSON, e JSON errado avisa
em vez de derrubar o app ou sumir com regra calado.

Rodar:
    python -m unittest discover tests
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["D3C_IDIOMA"] = "pt"  # as mensagens conferidas são as em português

from avaliador import avaliar, ler_builds, problemas_da_build  # noqa: E402
from builds_dos_testes import PASTA_DOS_TESTES  # noqa: E402

EXEMPLOS = RAIZ / "builds" / "exemplos"


def build_minima(**mudancas) -> dict:
    return {"formato": 1, "nome": "Teste", "classe": "Demon Hunter"} | mudancas


class TestSeguidor(unittest.TestCase):
    def test_seguidor_certo(self):
        b = build_minima(seguidor={"quem": "scoundrel", "itens": {"FingerL": "Unity"}, "habilidades": ["anatomy"]})
        self.assertEqual(problemas_da_build(b), [])

    def test_seguidor_errado_avisa(self):
        b = build_minima(seguidor={"quem": "lobo", "itens": {"Finger": "Unity"}, "habilidades": ["a"] * 5})
        texto = " ".join(problemas_da_build(b))
        self.assertIn("seguidor.quem", texto)
        self.assertIn("seguidor.itens: chave 'Finger'", texto)
        self.assertIn("até 4", texto)


class TestBuildsDoProjeto(unittest.TestCase):
    def test_todas_as_builds_estao_ok(self):
        _, problemas = ler_builds(PASTA_DOS_TESTES)
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

    def test_habilidades_cubo_e_fonte_certos(self):
        build = build_minima(
            habilidades={"ativas": [{"habilidade": "multishot", "runa": "a"}], "passivas": ["ambush"]},
            cubo={"arma": "Odyssey's End", "joia": "Ring of Royal Grandeur"},
            fonte={"site": "maxroll", "link": "https://maxroll.gg/d3/planner/1"})
        self.assertEqual(problemas_da_build(build), [])

    def test_habilidades_erradas(self):
        problemas = problemas_da_build(build_minima(habilidades={
            "ativas": [{"habilidade": "multishot", "runa": "z"}, "strafe", {"habilidade": "x", "rune": "a"}],
            "pasivas": [],
        }))
        self.assertEqual(len(problemas), 4, problemas)
        self.assertTrue(any("runa 'z' não existe" in p for p in problemas))
        self.assertTrue(any("'pasivas' não existe" in p and "'passivas'" in p for p in problemas))

    def test_paragon_certo_e_errado(self):
        certo = {"nivel": 5000, "pontos": [[3650, 650, 50, 50], [50] * 4, [50] * 4, [50] * 4]}
        self.assertEqual(problemas_da_build(build_minima(paragon=certo)), [])
        problemas = problemas_da_build(build_minima(paragon={"nivel": "5k", "pontos": [[1, 2, 3]], "x": 1}))
        self.assertEqual(len(problemas), 3, problemas)
        self.assertTrue(any("4 grupos de 4" in p for p in problemas))

    def test_limite_de_habilidades(self):
        sete = [{"habilidade": f"h{i}"} for i in range(7)]
        [problema] = problemas_da_build(build_minima(habilidades={"ativas": sete}))
        self.assertIn("até 6", problema)

    def test_cubo_errado(self):
        problemas = problemas_da_build(build_minima(cubo={"arma": "", "anel": "Focus"}))
        self.assertEqual(len(problemas), 2, problemas)


class TestCubo(unittest.TestCase):
    """Item do cubo de Kanai é da build mesmo sem os afixos (vale o poder lendário)."""

    def setUp(self):
        self.build = build_minima(
            todos_os_espacos={"obrigatorios": [{"modelo": "+# Dexterity", "rotulo": "Destreza"}]},
            espacos={"Weapon": {"itens": ["Yang's Recurve"]}},
            cubo={"arma": "Odyssey's End"})

    def arma(self, nome, classe=None):
        return {"nome": nome, "qualidade": "Legendary", "tipo": "Bow", "slot": "2-Hand",
                "classe": classe, "soquetes": 0, "primarios": [], "secundarios": []}

    def test_item_do_cubo_serve_sem_afixos(self):
        r = avaliar(self.arma("Odyssey's End"), self.build)
        self.assertTrue(r["bate"])
        self.assertEqual(r["motivo"], "Vai no cubo de Kanai (arma)")

    def test_outra_arma_continua_nao_servindo(self):
        r = avaliar(self.arma("Kridershot"), self.build)
        self.assertFalse(r["bate"])
        self.assertEqual(r["motivo"], "A build pede: Yang's Recurve")

    def test_item_do_cubo_de_outra_classe_nao_serve(self):
        self.assertFalse(avaliar(self.arma("Odyssey's End", classe="Barbarian"), self.build)["bate"])


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
