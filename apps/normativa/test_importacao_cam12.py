"""Testes de importação CAM 1.2: preservação, integridade e repetibilidade."""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Indicador, PesoIndicador, RegraIndicador, VersaoNormativa


class ImportacaoCAM12Tests(TestCase):
    def importar(self, **options):
        out = StringIO()
        call_command("importar_cam12", stdout=out, **options)
        return out.getvalue()

    def test_importa_catalogo_e_matriz_principal(self):
        self.importar()
        versao = VersaoNormativa.objects.get(codigo="CAM 1.2")
        self.assertIsNone(versao.vigencia_inicio)
        self.assertIsNone(versao.vigencia_fim)
        self.assertEqual(Indicador.objects.filter(versao=versao).count(), 58)
        self.assertEqual(
            set(Indicador.objects.filter(versao=versao, pai__isnull=True).values_list("codigo", flat=True)),
            {"1", "2", "3", "4", "5"},
        )
        self.assertEqual(PesoIndicador.objects.filter(indicador__versao=versao).count(), 44)
        self.assertEqual(RegraIndicador.objects.count(), 0)
        self.assertEqual(Indicador.objects.get(versao=versao, codigo="4.I.1").pai.codigo, "4.I")
        self.assertEqual(Indicador.objects.get(versao=versao, codigo="3.I.1").pai.codigo, "3.I")
        self.assertEqual(Indicador.objects.get(versao=versao, codigo="4.IV.2").pai.codigo, "4.IV")

    def test_pesos_principais_somam_cem_por_categoria(self):
        self.importar()
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        for categoria in Categoria.objects.all():
            pesos = PesoIndicador.objects.filter(
                categoria=categoria, indicador__versao__codigo="CAM 1.2", indicador__pai__isnull=True
            ).values_list("peso", flat=True)
            self.assertEqual(sum(pesos, Decimal("0")), Decimal("100"), categoria.codigo)
        self.assertFalse(
            PesoIndicador.objects.filter(indicador__codigo="1", categoria__codigo="CECON").exists()
        )
        self.assertFalse(
            PesoIndicador.objects.filter(indicador__codigo="5", categoria__codigo="USF").exists()
        )
        self.assertEqual(
            PesoIndicador.objects.get(indicador__codigo="4", categoria__codigo="USF").peso,
            Decimal("40"),
        )

    def test_importacao_repetida_nao_duplica_registros(self):
        self.importar()
        saida = self.importar()
        self.assertIn("Novos: 0 versão, 0 indicadores, 0 pesos", saida)
        self.assertEqual(VersaoNormativa.objects.filter(codigo="CAM 1.2").count(), 1)
        self.assertEqual(Indicador.objects.filter(versao__codigo="CAM 1.2").count(), 58)
        self.assertEqual(PesoIndicador.objects.count(), 44)

    def test_simulacao_nao_grava_dados(self):
        saida = self.importar(dry_run=True)
        self.assertIn("SIMULAÇÃO", saida)
        self.assertFalse(VersaoNormativa.objects.filter(codigo="CAM 1.2").exists())
        self.assertEqual(Indicador.objects.count(), 0)
        self.assertEqual(PesoIndicador.objects.count(), 0)

    def test_conflito_rejeitado_sem_substituir_dados_anteriores(self):
        versao = VersaoNormativa.objects.create(codigo="CAM 1.2", titulo="Versão já criada")
        indicador = Indicador.objects.create(versao=versao, codigo="1", nome="Rascunho manual")
        with self.assertRaisesRegex(CommandError, "Conflito em CAM 1.2/1"):
            self.importar()
        indicador.refresh_from_db()
        self.assertEqual(indicador.nome, "Rascunho manual")
        self.assertEqual(Indicador.objects.count(), 1)
        self.assertEqual(PesoIndicador.objects.count(), 0)

    def test_versao_existente_tem_vigencia_preservada(self):
        VersaoNormativa.objects.create(
            codigo="CAM 1.2", titulo="Cadastro existente", vigencia_inicio=date(2024, 9, 1)
        )
        self.importar()
        versao = VersaoNormativa.objects.get(codigo="CAM 1.2")
        self.assertEqual(versao.titulo, "Cadastro existente")
        self.assertEqual(versao.vigencia_inicio, date(2024, 9, 1))

    def test_pesos_excepcionais_nao_sao_ativados(self):
        self.importar()
        satisfacao = Indicador.objects.get(versao__codigo="CAM 1.2", codigo="3.I")
        self.assertIn("80.000%", satisfacao.descricao)
        self.assertIn("100.000%", satisfacao.descricao)
        self.assertFalse(PesoIndicador.objects.filter(indicador=satisfacao).exists())
        self.assertFalse(PesoIndicador.objects.filter(indicador__codigo="4.I.1").exists())
