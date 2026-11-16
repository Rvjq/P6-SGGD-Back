from datetime import date
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from .models import AutorizacaoColeta, CompetenciaColeta


class PainelConfiguradorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('importar_cam12', verbosity=0)
        call_command('configurar_regras_cam12', verbosity=0)
        Usuario = get_user_model()
        cls.config = Usuario.objects.create_user(username='pa-cfg',email='pa-cfg@exemplo.com',password='x')
        cls.config.groups.add(Group.objects.get(name='Configurador'))
        cls.reg = Usuario.objects.create_user(username='pa-reg',email='pa-reg@exemplo.com',password='x')
        cls.reg.groups.add(Group.objects.get(name='Registrador'))
        cls.comp = CompetenciaColeta.objects.create(mes=date(2026,11,1),versao=apps.get_model('normativa','VersaoNormativa').objects.get(codigo='CAM 1.2'))
        cls.unidade = apps.get_model('cadastro','Unidade').objects.create(
            codigo='PA-USF',nome='USF Painel',tipo=apps.get_model('cadastro','TipoUnidade').objects.get(codigo='USF'),
            distrito=apps.get_model('cadastro','Distrito').objects.get(codigo='I'))
        AutorizacaoColeta.objects.create(usuario=cls.reg,unidade=cls.unidade)

    def setUp(self):
        self.api = APIClient()

    def test_resumo_gerencial_com_contagens_e_progresso(self):
        self.api.force_authenticate(user=self.config)
        resp = self.api.get(f'/api/coleta/painel-configurador/?competencia={self.comp.pk}')
        self.assertEqual(resp.status_code,200,resp.data)
        self.assertEqual(resp.data['contagens']['usuarios'],2)
        self.assertEqual(resp.data['contagens']['unidades'],1)
        self.assertEqual(resp.data['contagens']['distritos'],8)
        self.assertEqual(resp.data['normativa']['codigo'],'CAM 1.2')
        self.assertEqual(len(resp.data['registradores']),1)
        self.assertGreater(resp.data['registradores'][0]['tarefas']['TOTAL'],0)

    def test_registrador_nao_consulta_gerencia(self):
        self.api.force_authenticate(user=self.reg)
        self.assertEqual(self.api.get('/api/coleta/painel-configurador/').status_code,403)
        self.api.force_authenticate(user=self.config)
        self.assertEqual(self.api.get('/api/coleta/painel-configurador/?competencia=errado').status_code,400)
