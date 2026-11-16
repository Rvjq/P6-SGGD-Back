"""Testes de regressão para preparação de base e massas de demonstração Recife.

Execute: python manage.py test apps.cadastro.test_comandos_recife
"""

from datetime import date
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .data.base_recife import MARCADOR_DESIGNACAO_DEMO, PREFIXO_DEMO
from .models import CategoriaAvaliacao, Distrito, PessoaAvaliada, Responsabilidade, TipoUnidade, Unidade
from .serializers import ResponsabilidadeSerializer
from django.core.exceptions import ValidationError as DjangoValidationError


@override_settings(DEBUG=True)
class PreparacaoBaseRecifeTests(TestCase):
    def executar(self, nome, *args, **options):
        saida = StringIO()
        call_command(nome, *args, stdout=saida, **options)
        return saida.getvalue()


    def test_unidade_implica_categoria_do_tipo_tambem_no_serializer(self):
        unidade = Unidade.objects.create(
            codigo="AV-U1", nome="USF exemplo", tipo=TipoUnidade.objects.get(codigo="USF"),
            distrito=Distrito.objects.get(codigo="I"),
        )
        pessoa = PessoaAvaliada.objects.create(codigo="AV-P1", nome="Pessoa teste")
        dados = {
            "pessoa": pessoa.pk, "unidade": unidade.pk,
            "data_inicio": "2026-01-01", "referencia_designacao": "Teste",
        }
        serializer = ResponsabilidadeSerializer(data=dados)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        responsabilidade = serializer.save()
        self.assertEqual(responsabilidade.categoria.codigo, "USF")

        categoria_caps = CategoriaAvaliacao.objects.get(codigo="CAPS")
        errado = ResponsabilidadeSerializer(data={**dados, "categoria": categoria_caps.pk})
        self.assertFalse(errado.is_valid())
        self.assertIn("categoria", errado.errors)
        with self.assertRaises(DjangoValidationError):
            Responsabilidade.objects.create(
                pessoa=pessoa, unidade=unidade, categoria=categoria_caps,
                data_inicio=date(2026, 2, 1),
            )

    def test_distrito_exige_categoria_funcional_explicita(self):
        pessoa = PessoaAvaliada.objects.create(codigo="AV-PD1", nome="Gestor distrital teste")
        distrito = Distrito.objects.get(codigo="I")
        sem_categoria = ResponsabilidadeSerializer(data={
            "pessoa": pessoa.pk, "distrito": distrito.pk, "data_inicio": "2026-01-01",
        })
        self.assertFalse(sem_categoria.is_valid())
        self.assertIn("categoria", sem_categoria.errors)
        categoria_gg = CategoriaAvaliacao.objects.get(codigo="GG")
        certo = ResponsabilidadeSerializer(data={
            "pessoa": pessoa.pk, "distrito": distrito.pk,
            "categoria": categoria_gg.pk, "data_inicio": "2026-01-01",
        })
        self.assertTrue(certo.is_valid(), certo.errors)
        self.assertEqual(certo.save().categoria.codigo, "GG")

    def test_preparar_base_completa_e_repetivel(self):
        self.executar("preparar_base_recife")
        Versao = apps.get_model("normativa", "VersaoNormativa")
        Indicador = apps.get_model("normativa", "Indicador")
        Peso = apps.get_model("normativa", "PesoIndicador")
        Regra = apps.get_model("normativa", "RegraIndicador")
        versao = Versao.objects.get(codigo="CAM 1.2")
        self.assertEqual(Distrito.objects.count(), 8)
        self.assertEqual(CategoriaAvaliacao.objects.count(), 11)
        self.assertEqual(TipoUnidade.objects.count(), 7)
        self.assertEqual(Indicador.objects.filter(versao=versao).count(), 58)
        self.assertEqual(Peso.objects.filter(indicador__versao=versao).count(), 44)
        self.assertEqual(Regra.objects.filter(indicador__versao=versao).count(), 157)

        segunda = self.executar("preparar_base_recife")
        self.assertIn("Novos: 0 distritos, 0 categorias, 0 tipos", segunda)
        self.assertIn("novas=0", segunda)
        self.assertEqual(Versao.objects.filter(codigo="CAM 1.2").count(), 1)
        self.assertEqual(Indicador.objects.filter(versao=versao).count(), 58)

    def test_dry_run_completo_nao_grava_normativa(self):
        Versao = apps.get_model("normativa", "VersaoNormativa")
        self.assertFalse(Versao.objects.filter(codigo="CAM 1.2").exists())
        saida = self.executar("preparar_base_recife", dry_run=True)
        self.assertIn("SIMULAÇÃO concluída", saida)
        self.assertFalse(Versao.objects.filter(codigo="CAM 1.2").exists())

    def test_estrutura_replica_migracao_sem_mudar_escopos(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        self.assertEqual(
            TipoUnidade.objects.get(codigo="UBT_MISTA").categoria.codigo, "UBT_MISTA"
        )
        self.assertEqual(CategoriaAvaliacao.objects.get(codigo="GG").escopo, "DISTRITO")
        self.assertEqual(Distrito.objects.count(), 8)
        self.assertEqual(Unidade.objects.count(), 0)

    def test_conflito_de_categoria_nao_e_sobrescrito(self):
        categoria = CategoriaAvaliacao.objects.get(codigo="GG")
        categoria.escopo = "UNIDADE"
        categoria.save(update_fields=["escopo"])
        with self.assertRaises(CommandError):
            self.executar("preparar_base_recife", apenas_estrutura=True)
        categoria.refresh_from_db()
        self.assertEqual(categoria.escopo, "UNIDADE")

    def test_rotulos_personalizados_nao_sao_sobrescritos_por_padrao(self):
        distrito = Distrito.objects.get(codigo="I")
        distrito.nome = "Nome customizado do Distrito I"
        distrito.save(update_fields=["nome"])
        self.executar("preparar_base_recife", apenas_estrutura=True)
        distrito.refresh_from_db()
        self.assertEqual(distrito.nome, "Nome customizado do Distrito I")
        self.executar("preparar_base_recife", apenas_estrutura=True, atualizar_rotulos=True)
        distrito.refresh_from_db()
        self.assertEqual(distrito.nome, "Distrito Sanitário I")

    def test_mock_das_sete_categorias_e_quatro_funcoes_distritais(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        Usuario = apps.get_model("acesso", "Usuario")
        usuarios_antes = Usuario.objects.count()
        self.executar("gerar_mock_recife")
        self.assertEqual(Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).count(), 21)
        self.assertEqual(PessoaAvaliada.objects.filter(codigo__startswith=PREFIXO_DEMO).count(), 53)
        self.assertEqual(Responsabilidade.objects.filter(
            referencia_designacao=MARCADOR_DESIGNACAO_DEMO
        ).count(), 53)
        self.assertEqual(Usuario.objects.count(), usuarios_antes)
        self.assertEqual(
            Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).values("distrito_id").distinct().count(), 8
        )
        unidade = Unidade.objects.get(codigo="DEMO-REC-U-UBT_MISTA-01")
        vinculo = Responsabilidade.objects.get(unidade=unidade)
        self.assertEqual(vinculo.categoria.codigo, "UBT_MISTA")
        self.assertEqual(vinculo.data_inicio, date(2026, 1, 1))
        for categoria in ["GG", "SNA", "SNB1", "SNB2"]:
            self.assertEqual(Responsabilidade.objects.filter(
                distrito__codigo="I", categoria__codigo=categoria,
                referencia_designacao=MARCADOR_DESIGNACAO_DEMO,
            ).count(), 1)

    def test_mock_e_idempotente_e_simulavel(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        self.executar("gerar_mock_recife", dry_run=True)
        self.assertFalse(Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).exists())
        self.executar("gerar_mock_recife", unidades_por_tipo=2)
        saida = self.executar("gerar_mock_recife", unidades_por_tipo=2)
        self.assertIn("novas unidades=0; pessoas=0; responsabilidades=0", saida)
        self.assertEqual(Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).count(), 14)

    def test_mock_pode_ampliar_quantidade_sem_mover_unidades(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        self.executar("gerar_mock_recife", unidades_por_tipo=1)
        unidade = Unidade.objects.get(codigo="DEMO-REC-U-USF-01")
        distrito_original = unidade.distrito_id
        self.executar("gerar_mock_recife", unidades_por_tipo=3)
        unidade.refresh_from_db()
        self.assertEqual(unidade.distrito_id, distrito_original)
        self.assertEqual(Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).count(), 21)

    def test_mock_nao_substitui_gestor_real_existente(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        usf = Unidade.objects.create(
            codigo="DEMO-REC-U-USF-01", nome="USF demonstrativa 01 [DEMO]",
            tipo=TipoUnidade.objects.get(codigo="USF"),
            distrito=Distrito.objects.get(codigo="I"),
        )
        pessoa_real = PessoaAvaliada.objects.create(codigo="AV-REAL-1", nome="Pessoa real")
        real = Responsabilidade.objects.create(
            pessoa=pessoa_real, categoria=usf.tipo.categoria,
            unidade=usf, data_inicio=date(2026, 1, 1),
            referencia_designacao="Designação institucional",
        )
        self.executar("gerar_mock_recife", unidades_por_tipo=1)
        self.assertTrue(Responsabilidade.objects.filter(pk=real.pk).exists())
        self.assertFalse(PessoaAvaliada.objects.filter(codigo="DEMO-REC-P-U-USF-01").exists())

    def test_mock_requer_estrutura_e_so_executa_em_debug(self):
        # Em ambiente de teste a migração já cria os catálogos; removendo um tipo
        # simulamos uma instalação incompleta da estrutura-base.
        tipo = TipoUnidade.objects.get(codigo="USF")
        tipo.delete()
        with self.assertRaises(CommandError):
            self.executar("gerar_mock_recife")
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                self.executar("gerar_mock_recife")

    def test_limpeza_so_apaga_dados_demo_e_exige_confirmacao(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        real = PessoaAvaliada.objects.create(codigo="REAL-TESTE", nome="Pessoa preservada")
        self.executar("gerar_mock_recife", unidades_por_tipo=1)
        self.executar("limpar_mock_recife", dry_run=True)
        self.assertTrue(Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).exists())
        with self.assertRaises(CommandError):
            self.executar("limpar_mock_recife")
        self.executar("limpar_mock_recife", confirmar=True)
        self.assertFalse(Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO).exists())
        self.assertFalse(PessoaAvaliada.objects.filter(codigo__startswith=PREFIXO_DEMO).exists())
        self.assertEqual(Responsabilidade.objects.filter(
            referencia_designacao=MARCADOR_DESIGNACAO_DEMO,
        ).count(), 0)
        self.assertTrue(PessoaAvaliada.objects.filter(pk=real.pk).exists())
        self.assertEqual(Distrito.objects.count(), 8)
        self.assertEqual(TipoUnidade.objects.count(), 7)

    def test_limpeza_recusa_remover_responsabilidade_real_em_unidade_mock(self):
        self.executar("preparar_base_recife", apenas_estrutura=True)
        self.executar("gerar_mock_recife", unidades_por_tipo=1)
        usf = Unidade.objects.get(codigo="DEMO-REC-U-USF-01")
        pessoa_real = PessoaAvaliada.objects.create(codigo="REAL-2", nome="Pessoa preservada")
        Responsabilidade.objects.create(
            pessoa=pessoa_real, categoria=usf.tipo.categoria,
            unidade=usf, data_inicio=date(2026, 1, 1),
            referencia_designacao="Ato real",
        )
        with self.assertRaises(CommandError):
            self.executar("limpar_mock_recife", confirmar=True)
        self.assertTrue(Unidade.objects.filter(pk=usf.pk).exists())
