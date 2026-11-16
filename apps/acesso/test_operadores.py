"""Acesso operacional: o Configurador não pode conceder privilégios administrativos."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient


class OperadoresAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.config = Usuario.objects.create_user(username="opcfg", email="opcfg@exemplo.com", password="teste")
        cls.reg = Usuario.objects.create_user(username="opreg", email="opreg@exemplo.com", password="teste")
        cls.super = Usuario.objects.create_superuser(username="opsuper", email="opsuper@exemplo.com", password="teste")
        cls.config.groups.add(Group.objects.get(name="Configurador"))
        cls.reg.groups.add(Group.objects.get(name="Registrador"))

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.config)

    def test_configurador_pode_criar_apenas_conta_operacional(self):
        resposta = self.client.post('/api/auth/operadores/', {
            'nome': 'Pessoa de Teste', 'email': 'nova@exemplo.com',
            'senha': 'SenhaTesteMuitoForte@2030', 'papel': 'Registrador'
        }, format='json')
        self.assertEqual(resposta.status_code, 201, resposta.data)
        novo = get_user_model().objects.get(email='nova@exemplo.com')
        self.assertFalse(novo.is_staff)
        self.assertFalse(novo.is_superuser)
        self.assertEqual(list(novo.groups.values_list('name', flat=True)), ['Registrador'])
        self.assertTrue(novo.check_password('SenhaTesteMuitoForte@2030'))

    def test_configurador_nao_eleva_privilegios(self):
        self.assertEqual(self.client.post('/api/auth/operadores/', {
            'nome': 'Super', 'email': 'supernovo@exemplo.com',
            'senha': 'SenhaTesteMuitoForte@2030', 'papel': 'Configurador'
        }, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/auth/operadores/{self.super.pk}/', {
            'papel': 'Registrador'
        }, format='json').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/auth/operadores/{self.config.pk}/', {
            'papel': 'Registrador'
        }, format='json').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/auth/operadores/{self.reg.pk}/', {
            'papel': 'Homologador'
        }, format='json').status_code, 400)

    def test_registrador_nao_cria_contas(self):
        self.client.force_authenticate(user=self.reg)
        self.assertEqual(self.client.get('/api/auth/operadores/').status_code, 403)
        self.assertEqual(self.client.post('/api/auth/operadores/', {
            'nome': 'Pessoa', 'email': 'pessoa@exemplo.com', 'senha': 'Senha@123456',
            'papel': 'Consultador'
        }, format='json').status_code, 403)
