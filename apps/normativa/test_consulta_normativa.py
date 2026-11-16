from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from .models import VersaoNormativa


class ConsultaNormativaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('importar_cam12', verbosity=0)
        call_command('configurar_regras_cam12', verbosity=0)
        Usuario = get_user_model()
        cls.cfg = Usuario.objects.create_user(username='n-cfg',email='n-cfg@exemplo.com',password='x')
        cls.cfg.groups.add(Group.objects.get(name='Configurador'))
        cls.reg = Usuario.objects.create_user(username='n-reg',email='n-reg@exemplo.com',password='x')
        cls.reg.groups.add(Group.objects.get(name='Registrador'))

    def setUp(self):
        self.api = APIClient()

    def test_versoes_e_detalhamento_reais(self):
        self.api.force_authenticate(user=self.cfg)
        lista = self.api.get('/api/normativa/versoes/')
        self.assertEqual(lista.status_code,200,lista.data)
        self.assertTrue(any(v['codigo']=='CAM 1.2' for v in lista.data))
        versao = VersaoNormativa.objects.get(codigo='CAM 1.2')
        resp = self.api.get(f'/api/normativa/versoes/{versao.pk}/')
        self.assertEqual(resp.status_code,200,resp.data)
        self.assertGreater(len(resp.data['indicadores']),0)
        self.assertGreater(len(resp.data['regras']),0)
        self.assertGreater(len(resp.data['pesos']),0)

    def test_registrador_nao_consulta_normativa_administrativa(self):
        self.api.force_authenticate(user=self.reg)
        self.assertEqual(self.api.get('/api/normativa/versoes/').status_code,403)
