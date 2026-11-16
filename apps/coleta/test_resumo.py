"""Resumo do dashboard: isolamento de permissões e contagem sem duplicidades."""
from datetime import date
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador


class ResumoColetaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("importar_cam12", verbosity=0)
        call_command("configurar_regras_cam12", verbosity=0)
        Usuario = get_user_model()
        cls.config = Usuario.objects.create_user(username="config-resumo", email="config-resumo@exemplo.com", password="teste")
        cls.reg = Usuario.objects.create_user(username="reg-resumo", email="reg-resumo@exemplo.com", password="teste")
        cls.outro = Usuario.objects.create_user(username="outro-resumo", email="outro-resumo@exemplo.com", password="teste")
        cls.hom = Usuario.objects.create_user(username="hom-resumo", email="hom-resumo@exemplo.com", password="teste")
        cls.cons = Usuario.objects.create_user(username="cons-resumo", email="cons-resumo@exemplo.com", password="teste")
        for usuario, grupo in [(cls.config,"Configurador"),(cls.reg,"Registrador"),
                               (cls.outro,"Registrador"),(cls.hom,"Homologador"),(cls.cons,"Consultador")]:
            usuario.groups.add(Group.objects.get(name=grupo))
        Distrito = apps.get_model("cadastro", "Distrito")
        Tipo = apps.get_model("cadastro", "TipoUnidade")
        Unidade = apps.get_model("cadastro", "Unidade")
        Versao = apps.get_model("normativa", "VersaoNormativa")
        cls.d = Distrito.objects.get(codigo="I")
        cls.d2 = Distrito.objects.get(codigo="II")
        cls.usf = Unidade.objects.create(codigo="R-USF", nome="USF Resumo", distrito=cls.d, tipo=Tipo.objects.get(codigo="USF"))
        cls.caps = Unidade.objects.create(codigo="R-CAPS", nome="CAPS Resumo", distrito=cls.d2, tipo=Tipo.objects.get(codigo="CAPS"))
        cls.comp = CompetenciaColeta.objects.create(mes=date(2026,11,1), versao=Versao.objects.get(codigo="CAM 1.2"))
        AutorizacaoColeta.objects.create(usuario=cls.reg, unidade=cls.usf)
        AutorizacaoColeta.objects.create(usuario=cls.outro, unidade=cls.usf)  # mesmo escopo não duplica progresso
        AutorizacaoColeta.objects.create(usuario=cls.outro, unidade=cls.caps)

    def setUp(self):
        self.api = APIClient()

    def buscar(self, usuario):
        self.api.force_authenticate(user=usuario)
        return self.api.get(f"/api/coleta/resumo/?competencia={self.comp.pk}")

    def test_necessita_autenticacao_e_periodo(self):
        self.assertIn(self.api.get(f"/api/coleta/resumo/?competencia={self.comp.pk}").status_code, (401, 403))
        self.api.force_authenticate(user=self.reg)
        self.assertEqual(self.api.get("/api/coleta/resumo/").status_code, 400)
        self.assertEqual(self.api.get("/api/coleta/resumo/?competencia=999999").status_code, 404)

    def test_registrador_ve_apenas_seu_escopo(self):
        dados = self.buscar(self.reg).data
        self.assertEqual(dados["perfil"], "REGISTRADOR")
        self.assertEqual(dados["escopos"], 1)
        self.assertGreater(dados["tarefas"]["TOTAL"], 0)
        self.assertEqual(dados["tarefas"]["ENVIADA"], 0)

    def test_configurador_vê_unidades_únicas_e_atividade_real(self):
        dados = self.buscar(self.config).data
        self.assertEqual(dados["perfil"], "CONFIGURADOR")
        self.assertEqual(dados["escopos"], 2)
        self.assertEqual(dados["atribuicoes"], 3)
        self.assertEqual(dados["operadores"], 2)
        self.assertGreater(dados["tarefas"]["TOTAL"], 0)

    def test_homologador_somente_lancamentos_reais(self):
        dados = self.buscar(self.hom).data
        self.assertEqual(dados["perfil"], "HOMOLOGADOR")
        self.assertEqual(dados["tarefas"]["TOTAL"], 0)
        # Um registro enviado compõe um grupo de revisão.
        Indicador = apps.get_model("normativa", "Indicador")
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        registro = RegistroIndicador.objects.create(
            competencia=self.comp, indicador=Indicador.objects.get(versao=self.comp.versao, codigo="1"),
            categoria=Categoria.objects.get(codigo="USF"), unidade=self.usf,
            dados={"valor": 100}, fonte="Teste", registrado_por=self.reg, situacao="ENVIADO")
        dados = self.buscar(self.hom).data
        self.assertEqual(dados["tarefas"]["ENVIADA"], 1)
        self.assertEqual(dados["tarefas"]["TOTAL"], 1)
        registro.situacao="HOMOLOGADO"; registro.homologado_por=self.hom; registro.save()
        dados = self.buscar(self.hom).data
        self.assertEqual(dados["tarefas"]["HOMOLOGADA"], 1)
        self.assertEqual(dados["tarefas"]["ENVIADA"], 0)

    def test_consultador_nao_recebe_dados_de_coleta(self):
        dados = self.buscar(self.cons).data
        self.assertEqual(dados["perfil"], "CONSULTADOR")
        self.assertIsNone(dados["tarefas"])
        self.assertEqual(dados["escopos"], 0)
