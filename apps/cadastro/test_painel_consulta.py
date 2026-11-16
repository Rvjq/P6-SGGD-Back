from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from .models import CategoriaAvaliacao, Distrito, PessoaAvaliada, Responsabilidade, TipoUnidade, Unidade


class PainelCadastroTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.config = Usuario.objects.create_user(username="painel-cfg", email="painel-cfg@exemplo.com", password="x")
        self.config.groups.add(Group.objects.get(name="Configurador"))
        self.reg = Usuario.objects.create_user(username="painel-reg", email="painel-reg@exemplo.com", password="x")
        self.reg.groups.add(Group.objects.get(name="Registrador"))
        d = Distrito.objects.get(codigo="I")
        self.usf = Unidade.objects.create(codigo="PX-USF", nome="Unidade de exemplo", distrito=d,
                                          tipo=TipoUnidade.objects.get(codigo="USF"))
        self.pessoa = PessoaAvaliada.objects.create(codigo="AV-PX", nome="Ana de Teste")
        Responsabilidade.objects.create(pessoa=self.pessoa, unidade=self.usf,
                                        categoria=CategoriaAvaliacao.objects.get(codigo="USF"),
                                        data_inicio=date(2026, 11, 20), data_fim=date(2026, 12, 5))
        self.api = APIClient()

    def test_competencia_considera_vigencia_no_mes(self):
        self.api.force_authenticate(user=self.config)
        resp = self.api.get('/api/cadastro/painel/?mes=2026-11')
        self.assertEqual(resp.status_code, 200, resp.data)
        unidade = next(u for u in resp.data['unidades'] if u['id'] == self.usf.pk)
        self.assertEqual(unidade['responsaveis'][0]['pessoa'], 'Ana de Teste')
        resp = self.api.get('/api/cadastro/painel/?mes=2026-10')
        unidade = next(u for u in resp.data['unidades'] if u['id'] == self.usf.pk)
        self.assertEqual(unidade['responsaveis'], [])

    def test_parametro_errado_e_acesso_negado(self):
        self.api.force_authenticate(user=self.config)
        self.assertEqual(self.api.get('/api/cadastro/painel/?mes=novembro').status_code, 400)
        self.api.force_authenticate(user=self.reg)
        self.assertEqual(self.api.get('/api/cadastro/painel/?mes=2026-11').status_code, 403)
