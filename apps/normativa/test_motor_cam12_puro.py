"""Testes que podem ser executados também sem Django instalado."""
from decimal import Decimal
import unittest
from pathlib import Path
import json

from .services.calculo_cam12 import (
    RegraPendente, calcular, consolidar_pontuacao, nota_percentual,
    nota_por_faixas, media, media_ponderada,
)

REGRAS = json.loads((Path(__file__).parent / "data" / "regras_cam12.json").read_text(encoding="utf-8"))["regras"]


def obter(codigo, categoria):
    for bloco in REGRAS[codigo]:
        if categoria in bloco["categorias"]:
            return bloco
    raise KeyError((codigo, categoria))


class FormulaCAM12Tests(unittest.TestCase):
    def test_1_unidade_18_de_20_dá_zero(self):
        self.assertEqual(calcular(obter("1", "USF"), {"numerador":18,"denominador":20}), 0)
        self.assertEqual(calcular(obter("1", "USF"), {"numerador":20,"denominador":20}), 100)

    def test_1_distrito_bandas(self):
        r=obter("1", "GG")
        for n,esperado in [(6,0),(7,50),(8,50),(9,75),(10,100)]:
            self.assertEqual(calcular(r, {"numerador":n,"denominador":10}), esperado)

    def test_2_gestao_trabalho_unidade_e_distrito(self):
        cods=["2.1", "2.2", "2.3", "2.4"]
        self.assertEqual(calcular(obter("2.2", "USF"), {"valor":0}),100)
        self.assertEqual(calcular(obter("2.2", "USF"), {"valor":1}),0)
        self.assertEqual(calcular(obter("2.3", "USF"), {"numerador":12,"denominador":20}),50)
        self.assertEqual(calcular(obter("2", "USF"), {"notas": dict(zip(cods,[100,0,50,100]))}),50)
        self.assertEqual(calcular(obter("2", "GG"), {"notas":[100,0,50]}),50)

    def test_3_asu_avaliacoes(self):
        self.assertEqual(calcular(obter("3.II", "USF"), {"numerador":2,"denominador":100}),50)
        self.assertEqual(calcular(obter("3.I.2", "CAPS"), {"valor":20}),80)
        self.assertEqual(calcular(obter("3.I.3", "UCIS"), {"valor":45}),100)
        self.assertEqual(calcular(obter("3.I", "USF"), {"nota":80,"origem_confirmada":True}),80)
        with self.assertRaises(RegraPendente):
            calcular(obter("3", "USF"), {"notas":{"3.I":90,"3.II":50}})

    def test_4_desempenho_metodos(self):
        self.assertEqual(calcular(obter("4.I.1", "USF"), {"valor":45}),100)
        self.assertEqual(calcular(obter("4.II.3", "CAPS"), {"valor":80}),100)
        self.assertEqual(calcular(obter("4.III", "UBT"), {"notas":[100,50]}),75)
        self.assertEqual(calcular(obter("4.VII.3.1", "MAC"), {"valor":67}),50)
        self.assertEqual(calcular(obter("4.VII.3.2", "MAC"), {"valor":62}),75)
        self.assertEqual(calcular(obter("4.VI", "GG"), {"notas":[60,80,100]}),80)
        with self.assertRaises(RegraPendente):
            calcular(obter("4.I", "USF"), {"equipes":[]})
        with self.assertRaises(RegraPendente):
            calcular(obter("4.IV.2", "UCIS"), {"valor":80})

    def test_5_vigilancia_media_e_metodos(self):
        self.assertEqual(calcular(obter("5.I", "SNB1"), {"valor":70}),100)
        self.assertEqual(calcular(obter("5.II", "SNB1"), {"valor":40}),50)
        self.assertEqual(calcular(obter("5.I", "SNB1"), {"numerador":0,"denominador":0,"sem_ocorrencias_confirmado":True}),100)
        with self.assertRaises(RegraPendente):
            calcular(obter("5.I", "SNB1"), {"numerador":0,"denominador":0})
        self.assertEqual(calcular(obter("5", "GG"), {"notas":{"5.I":100,"5.II":50,"5.III":100}}),Decimal("83.33333333333333333333333333"))

    def test_regras_sem_denominador_nao_inventam_zero(self):
        with self.assertRaises(ValueError):
            nota_percentual(0,0)
        with self.assertRaises(ValueError):
            nota_percentual(11,10)

    def test_peso_inabil_apenas_se_declarado(self):
        pesos={"1":20,"2":20,"3":20,"4":40}
        self.assertEqual(consolidar_pontuacao(pesos,{"1":0,"2":100,"3":100,"4":100}),80)
        self.assertEqual(consolidar_pontuacao(pesos,{"2":100,"3":100,"4":100},inaptos={"1"}),100)
        with self.assertRaises(ValueError):
            consolidar_pontuacao(pesos,{"2":100,"3":100,"4":100})


if __name__ == "__main__":
    unittest.main()
