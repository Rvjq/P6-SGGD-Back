from datetime import date
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from .models import CompetenciaColeta, AutorizacaoColeta


class TarefasComAvaliadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('importar_cam12', verbosity=0)
        call_command('configurar_regras_cam12', verbosity=0)
        Usuario = get_user_model()
        cls.reg = Usuario.objects.create_user(username='resp-reg',email='resp-reg@exemplo.com',password='x')
        cls.reg.groups.add(Group.objects.get(name='Registrador'))
        cls.outro = Usuario.objects.create_user(username='resp-outro',email='resp-outro@exemplo.com',password='x')
        cls.outro.groups.add(Group.objects.get(name='Registrador'))
        Cadastro = lambda modelo: apps.get_model('cadastro',modelo)
        distrito = Cadastro('Distrito').objects.get(codigo='I')
        cls.usf = Cadastro('Unidade').objects.create(codigo='T-RESP',nome='USF designada',distrito=distrito,
                                    tipo=Cadastro('TipoUnidade').objects.get(codigo='USF'))
        pessoa = Cadastro('PessoaAvaliada').objects.create(codigo='P-RESP',nome='Gestora Exemplo')
        Cadastro('Responsabilidade').objects.create(pessoa=pessoa,unidade=cls.usf,
               categoria=Cadastro('CategoriaAvaliacao').objects.get(codigo='USF'),data_inicio=date(2026,10,1))
        versao = apps.get_model('normativa','VersaoNormativa').objects.get(codigo='CAM 1.2')
        cls.comp = CompetenciaColeta.objects.create(mes=date(2026,11,1),versao=versao)
        AutorizacaoColeta.objects.create(usuario=cls.reg,unidade=cls.usf)

    def setUp(self):
        self.api = APIClient()

    def test_responsavel_aparece_somente_em_escopo_autorizado(self):
        self.api.force_authenticate(user=self.reg)
        resp = self.api.get(f'/api/coleta/tarefas/?competencia={self.comp.pk}')
        self.assertEqual(resp.status_code,200,resp.data)
        alvo = next(e for e in resp.data['escopos'] if e['id']==self.usf.pk)
        self.assertEqual(alvo['responsaveis'][0]['nome'],'Gestora Exemplo')
        self.api.force_authenticate(user=self.outro)
        fora = self.api.get(f'/api/coleta/tarefas/?competencia={self.comp.pk}')
        self.assertEqual(fora.status_code,200)
        self.assertEqual(fora.data['escopos'],[])
