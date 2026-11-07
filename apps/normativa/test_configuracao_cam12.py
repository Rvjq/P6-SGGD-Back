"""Testes Django para a etapa de configuração de regras CAM 1.2."""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Indicador, RegraIndicador


class ConfiguracaoRegrasCAM12Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("importar_cam12", stdout=StringIO())

    def configurar(self, **kwargs):
        out = StringIO()
        call_command("configurar_regras_cam12", stdout=out, **kwargs)
        return out.getvalue()

    def test_regras_para_todos_os_58_indicadores(self):
        self.configurar()
        self.assertEqual(RegraIndicador.objects.count(), 157)
        self.assertEqual(
            RegraIndicador.objects.values("indicador_id").distinct().count(), 58
        )
        self.assertEqual(
            RegraIndicador.objects.get(indicador__codigo="1", categoria__codigo="USF").meta_valor,
            Decimal("100"),
        )
        self.assertEqual(
            RegraIndicador.objects.get(indicador__codigo="4.I.1", categoria__codigo="USF").meta_valor,
            Decimal("45"),
        )
        regra = RegraIndicador.objects.get(indicador__codigo="4.IV.2", categoria__codigo="UCIS")
        self.assertEqual(regra.parametros["status"], "REVISAR")

    def test_simulacao_nao_altera_banco(self):
        self.configurar(dry_run=True)
        self.assertFalse(RegraIndicador.objects.exists())

    def test_idempotente(self):
        self.configurar()
        result = self.configurar()
        self.assertIn("novas=0", result)
        self.assertEqual(RegraIndicador.objects.count(), 157)

    def test_conflito_interrompe_e_reverte_operacao(self):
        codigo = Indicador.objects.get(codigo="1", versao__codigo="CAM 1.2")
        from django.apps import apps
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        RegraIndicador.objects.create(
            indicador=codigo,
            categoria=Categoria.objects.get(codigo="USF"),
            metodo=RegraIndicador.Metodo.NOTA_INFORMADA,
        )
        with self.assertRaisesRegex(CommandError, "Regra já existente e diferente"):
            self.configurar()
        self.assertEqual(RegraIndicador.objects.count(), 1)
