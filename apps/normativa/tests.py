"""Testes da estrutura da Normativa. Não valida cálculos CAM 1.2 nesta etapa."""

from datetime import date
from decimal import Decimal

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from .models import Indicador, PesoIndicador, RegraIndicador, VersaoNormativa


class NormativaEstruturaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Obtém o Cadastro pelo registro de apps: sem dependência de importação
        # direta entre os componentes do monólito modular.
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        cls.usf = Categoria.objects.get(codigo="USF")
        cls.gg = Categoria.objects.get(codigo="GG")
        cls.versao = VersaoNormativa.objects.create(
            codigo="CAM 1.2", titulo="Matriz de referência CAM 1.2"
        )
        cls.medicamentos = Indicador.objects.create(
            versao=cls.versao, codigo="1", nome="Registro de medicamentos"
        )

    def test_versao_sem_vigencia_presumida(self):
        self.assertIsNone(self.versao.vigencia_inicio)
        self.assertIsNone(self.versao.vigencia_fim)

    def test_versao_rejeita_intervalo_invertido(self):
        with self.assertRaises(ValidationError):
            VersaoNormativa.objects.create(
                codigo="CAM TESTE", titulo="Exemplo", vigencia_inicio=date(2026, 10, 1),
                vigencia_fim=date(2026, 9, 30),
            )

    def test_codigo_da_versao_e_unico(self):
        with self.assertRaises(ValidationError):
            VersaoNormativa.objects.create(codigo="CAM 1.2", titulo="Duplicada")

    def test_hierarquia_de_tres_niveis(self):
        principal = Indicador.objects.create(
            versao=self.versao, codigo="4", nome="Desempenho"
        )
        variante = Indicador.objects.create(
            versao=self.versao, codigo="4.I", nome="Desempenho ESF", pai=principal
        )
        folha = Indicador.objects.create(
            versao=self.versao, codigo="4.I.1", nome="Pré-natal", pai=variante
        )
        self.assertEqual(folha.pai, variante)
        self.assertEqual(variante.pai, principal)
        self.assertEqual(principal.filhos.count(), 1)

    def test_codigo_de_indicador_unico_apenas_na_mesma_versao(self):
        with self.assertRaises(ValidationError):
            Indicador.objects.create(
                versao=self.versao, codigo="1", nome="Código repetido"
            )
        outra = VersaoNormativa.objects.create(codigo="OUTRA", titulo="Outra versão")
        indicador = Indicador.objects.create(
            versao=outra, codigo="1", nome="Mesmo código em outra versão"
        )
        self.assertEqual(indicador.codigo, self.medicamentos.codigo)

    def test_pai_de_outra_versao_e_rejeitado(self):
        outra = VersaoNormativa.objects.create(codigo="OUTRA", titulo="Outra versão")
        with self.assertRaises(ValidationError):
            Indicador.objects.create(
                versao=outra, codigo="4.I", nome="Inválido", pai=self.medicamentos
            )

    def test_hierarquia_rejeita_ciclos(self):
        filho = Indicador.objects.create(
            versao=self.versao, codigo="1.I", nome="Filho", pai=self.medicamentos
        )
        self.medicamentos.pai = filho
        with self.assertRaises(ValidationError):
            self.medicamentos.save()
        self.medicamentos.refresh_from_db()
        self.assertIsNone(self.medicamentos.pai)

    def test_indicador_nao_pode_ser_seu_proprio_pai(self):
        self.medicamentos.pai = self.medicamentos
        with self.assertRaises(ValidationError):
            self.medicamentos.save()

    def test_regra_por_categoria_da_mesma_versao(self):
        regra_usf = RegraIndicador.objects.create(
            indicador=self.medicamentos, categoria=self.usf,
            metodo=RegraIndicador.Metodo.PROPORCAO,
            meta_valor=Decimal("100"),
            meta_comparador=RegraIndicador.Comparador.MAIOR_IGUAL,
            meta_unidade="%", parametros={"prazo_dias_uteis": 2},
        )
        regra_gg = RegraIndicador.objects.create(
            indicador=self.medicamentos, categoria=self.gg,
            metodo=RegraIndicador.Metodo.FAIXAS,
            parametros={"observacao": "Regras distritais ainda não importadas"},
        )
        self.assertEqual(regra_usf.indicador.versao, self.versao)
        self.assertEqual(regra_gg.categoria.codigo, "GG")
        self.assertEqual(self.medicamentos.regras.count(), 2)

    def test_regra_rejeita_duplicacao_de_categoria_e_indicador(self):
        RegraIndicador.objects.create(indicador=self.medicamentos, categoria=self.usf)
        with self.assertRaises(ValidationError):
            RegraIndicador.objects.create(indicador=self.medicamentos, categoria=self.usf)

    def test_regra_exige_comparador_para_meta_numerica(self):
        with self.assertRaises(ValidationError):
            RegraIndicador.objects.create(
                indicador=self.medicamentos, categoria=self.usf, meta_valor=Decimal("100")
            )

    def test_regra_nao_aceita_parametros_como_lista(self):
        with self.assertRaises(ValidationError):
            RegraIndicador.objects.create(
                indicador=self.medicamentos, categoria=self.usf, parametros=[1, 2]
            )

    def test_pesos_por_categoria_independentes(self):
        PesoIndicador.objects.create(
            indicador=self.medicamentos, categoria=self.usf, peso=Decimal("20")
        )
        PesoIndicador.objects.create(
            indicador=self.medicamentos, categoria=self.gg, peso=Decimal("20")
        )
        self.assertEqual(self.medicamentos.pesos.count(), 2)

    def test_peso_rejeita_valor_fora_do_intervalo(self):
        for valor in (Decimal("-1"), Decimal("100.1")):
            with self.subTest(valor=valor):
                with self.assertRaises(ValidationError):
                    PesoIndicador.objects.create(
                        indicador=self.medicamentos, categoria=self.usf, peso=valor
                    )

    def test_peso_tambem_pode_existir_em_subindicador(self):
        filho = Indicador.objects.create(
            versao=self.versao, codigo="1.1", nome="Subindicador", pai=self.medicamentos
        )
        peso = PesoIndicador.objects.create(
            indicador=filho, categoria=self.usf, peso=Decimal("25")
        )
        self.assertEqual(peso.indicador.pai, self.medicamentos)

    def test_peso_unico_por_categoria_e_indicador(self):
        PesoIndicador.objects.create(indicador=self.medicamentos, categoria=self.usf, peso=20)
        with self.assertRaises(ValidationError):
            PesoIndicador.objects.create(indicador=self.medicamentos, categoria=self.usf, peso=30)

    def test_indicador_e_categoria_protegidos_contra_exclusao(self):
        PesoIndicador.objects.create(indicador=self.medicamentos, categoria=self.usf, peso=20)
        with self.assertRaises(ProtectedError):
            self.medicamentos.delete()
        with self.assertRaises(ProtectedError):
            self.usf.delete()
        with self.assertRaises(ProtectedError):
            self.versao.delete()

    def test_modelos_disponiveis_no_admin(self):
        for modelo in (VersaoNormativa, Indicador, RegraIndicador, PesoIndicador):
            self.assertTrue(admin.site.is_registered(modelo))
