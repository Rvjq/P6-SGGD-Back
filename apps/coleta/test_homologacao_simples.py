"""Regressões da homologação simples e da consulta de decisões.

Execute: python manage.py test apps.coleta.test_homologacao_simples
"""
from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import CompetenciaColeta, RegistroIndicador


class HomologacaoSimplesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("importar_cam12", verbosity=0)
        call_command("configurar_regras_cam12", verbosity=0)
        User = get_user_model()
        cls.autor = User.objects.create_user(username="hom-autor", email="autor.hom@exemplo.com", password="teste")
        cls.revisor = User.objects.create_user(username="hom-revisor", email="revisor.hom@exemplo.com", password="teste")
        cls.outro = User.objects.create_user(username="hom-outro", email="outro.hom@exemplo.com", password="teste")
        cls.revisor.groups.add(Group.objects.get(name="Homologador"))
        cls.autor.groups.add(Group.objects.get(name="Registrador"))
        cls.outro.groups.add(Group.objects.get(name="Consultador"))

        Versao = apps.get_model("normativa", "VersaoNormativa")
        Indicador = apps.get_model("normativa", "Indicador")
        TipoUnidade = apps.get_model("cadastro", "TipoUnidade")
        Unidade = apps.get_model("cadastro", "Unidade")
        Distrito = apps.get_model("cadastro", "Distrito")
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        Pessoa = apps.get_model("cadastro", "PessoaAvaliada")
        Responsabilidade = apps.get_model("cadastro", "Responsabilidade")

        cls.versao = Versao.objects.get(codigo="CAM 1.2")
        cls.competencia = CompetenciaColeta.objects.create(mes=date(2026, 11, 1), versao=cls.versao)
        cls.distrito = Distrito.objects.get(codigo="I")
        cls.unidade = Unidade.objects.create(
            codigo="HOM-UN-01", nome="USF de homologação", distrito=cls.distrito,
            tipo=TipoUnidade.objects.get(codigo="USF"),
        )
        cls.categoria = cls.unidade.tipo.categoria
        cls.indicador = Indicador.objects.get(versao=cls.versao, codigo="1")
        cls.indicador_i4 = Indicador.objects.get(versao=cls.versao, codigo="4.I.1")
        cls.pessoa = Pessoa.objects.create(codigo="HOM-P-01", nome="Responsável Exemplo")
        Responsabilidade.objects.create(
            pessoa=cls.pessoa, unidade=cls.unidade, categoria=cls.categoria,
            data_inicio=date(2026, 1, 1),
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=self.revisor)

    def criar_registro(self, indicador=None):
        return RegistroIndicador.objects.create(
            competencia=self.competencia, unidade=self.unidade, categoria=self.categoria,
            indicador=indicador or self.indicador, registrado_por=self.autor,
            dados={"numerador": 18, "denominador": 20} if indicador is None else {"valor": 92},
            fonte="Sistema técnico de testes", situacao=RegistroIndicador.Situacao.ENVIADO,
        )

    def consultar(self, situacao=None):
        sufixo = f"&situacao={situacao}" if situacao else ""
        return self.api.get(f"/api/coleta/tarefas/revisao/?competencia={self.competencia.pk}{sufixo}")

    def decidir(self, ids, decisao="HOMOLOGAR", motivo=""):
        return self.api.post('/api/coleta/tarefas/decidir/', {
            "ids": ids, "decisao": decisao, "motivo": motivo,
        }, format="json")

    def test_pendentes_por_padrao_incluem_fonte_e_responsavel(self):
        registro = self.criar_registro()
        resposta = self.consultar()
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(len(resposta.data), 1)
        grupo = resposta.data[0]
        self.assertEqual(grupo["situacao"], "ENVIADO")
        self.assertEqual(grupo["distrito_grupo"], self.distrito.pk)
        self.assertEqual(grupo["distrito_nome"], self.distrito.nome)
        self.assertEqual(grupo["registrador_email"], self.autor.email)
        self.assertEqual(grupo["itens"][0]["id"], registro.pk)
        self.assertEqual(grupo["itens"][0]["fonte"], "Sistema técnico de testes")
        self.assertEqual(grupo["responsaveis"][0]["nome"], "Responsável Exemplo")

    def test_homologados_aparecem_somente_no_historico_atual(self):
        registro = self.criar_registro()
        resposta = self.decidir([registro.pk])
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["situacao"], "HOMOLOGADO")
        self.assertEqual(self.consultar().data, [])
        homologados = self.consultar("HOMOLOGADO").data
        self.assertEqual(len(homologados), 1)
        self.assertEqual(homologados[0]["revisado_por"], self.revisor.email)
        self.assertIsNotNone(homologados[0]["decidido_em"])
        self.assertEqual(self.consultar("TODOS").data[0]["situacao"], "HOMOLOGADO")
        registro.refresh_from_db()
        self.assertEqual(registro.homologado_por, self.revisor)

    def test_devolucao_exige_motivo_e_exibe_justificativa(self):
        registro = self.criar_registro()
        self.assertEqual(self.decidir([registro.pk], "DEVOLVER").status_code, 400)
        self.assertEqual(self.decidir([registro.pk], "DEVOLVER", motivo=123).status_code, 400)
        resposta = self.decidir([registro.pk], "DEVOLVER", "  Conferir planilha  ")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        devolvidos = self.consultar("DEVOLVIDO").data
        self.assertEqual(devolvidos[0]["motivo_devolucao"], "Conferir planilha")
        self.assertEqual(self.consultar().data, [])

    def test_nao_permite_dupla_decisao(self):
        registro = self.criar_registro()
        self.assertEqual(self.decidir([registro.pk]).status_code, 200)
        self.assertEqual(self.decidir([registro.pk], "DEVOLVER", "Não pode").status_code, 400)

    def test_nao_permite_homologar_so_um_subindicador_enviado(self):
        primeiro = self.criar_registro(indicador=self.indicador_i4)
        segundo_indicador = apps.get_model("normativa", "Indicador").objects.get(
            versao=self.versao, codigo="4.I.2",
        )
        segundo = self.criar_registro(indicador=segundo_indicador)
        self.assertEqual(self.decidir([primeiro.pk]).status_code, 400)
        primeiro.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primeiro.situacao, "ENVIADO")
        self.assertEqual(segundo.situacao, "ENVIADO")
        self.assertEqual(self.decidir([primeiro.pk, segundo.pk]).status_code, 200)

    def test_nao_permite_unir_indicadores_diferentes(self):
        primeiro = self.criar_registro()
        segundo = self.criar_registro(indicador=self.indicador_i4)
        self.assertEqual(self.decidir([primeiro.pk, segundo.pk]).status_code, 400)
        self.assertEqual(RegistroIndicador.objects.filter(situacao="ENVIADO").count(), 2)

    def test_permissoes_e_autorrevisao(self):
        registro = self.criar_registro()
        self.api.force_authenticate(user=self.outro)
        self.assertEqual(self.consultar().status_code, 403)
        self.assertEqual(self.decidir([registro.pk]).status_code, 403)
        self.api.force_authenticate(user=self.autor)
        self.autor.groups.add(Group.objects.get(name="Homologador"))
        self.assertEqual(self.decidir([registro.pk]).status_code, 403)
        registro.refresh_from_db()
        self.assertEqual(registro.situacao, "ENVIADO")

    def test_consulta_separa_situacoes_do_mesmo_indicador(self):
        primeiro = self.criar_registro(indicador=self.indicador_i4)
        segundo_indicador = apps.get_model("normativa", "Indicador").objects.get(
            versao=self.versao, codigo="4.I.2",
        )
        segundo = self.criar_registro(indicador=segundo_indicador)
        segundo.situacao = "HOMOLOGADO"
        segundo.homologado_por = self.revisor
        segundo.save()
        todos = self.consultar("TODOS")
        self.assertEqual(todos.status_code, 200, todos.data)
        self.assertEqual(len(todos.data), 2)
        self.assertEqual({g["situacao"] for g in todos.data}, {"ENVIADO", "HOMOLOGADO"})
        self.assertEqual(len(self.consultar().data), 1)
        self.assertEqual(self.decidir([primeiro.pk]).status_code, 200)

    def test_filtros_invalidos(self):
        self.assertEqual(self.consultar("EXCLUIDO").status_code, 400)
        self.assertEqual(self.api.get("/api/coleta/tarefas/revisao/").status_code, 400)
        self.assertEqual(self.decidir([0]).status_code, 400)
        self.assertEqual(self.decidir([1, 1]).status_code, 400)
        self.assertEqual(self.decidir([True]).status_code, 400)
