from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient


class ConsultaUsuariosTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.config = Usuario.objects.create_user(username="cfg-usuarios", email="cfg-usuarios@exemplo.com", password="teste")
        self.config.groups.add(Group.objects.get(name="Configurador"))
        self.reg = Usuario.objects.create_user(username="reg-usuarios", email="reg-usuarios@exemplo.com", password="teste")
        self.reg.groups.add(Group.objects.get(name="Registrador"))
        self.admin = Usuario.objects.create_superuser(username="admin-usuarios", email="admin-usuarios@exemplo.com", password="teste")
        self.api = APIClient()

    def test_configurador_ve_todos_sem_dados_secretos(self):
        self.api.force_authenticate(user=self.config)
        resposta = self.api.get("/api/auth/usuarios/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(len(resposta.data), 3)
        por_id = {u["id"]: u for u in resposta.data}
        self.assertTrue(por_id[self.reg.pk]["administravel"])
        self.assertFalse(por_id[self.admin.pk]["administravel"])
        self.assertNotIn("password", por_id[self.admin.pk])

    def test_registrador_nao_consulta_contas(self):
        self.api.force_authenticate(user=self.reg)
        self.assertEqual(self.api.get("/api/auth/usuarios/").status_code, 403)

    def test_criacao_com_sobrenome_cargo_nao_eleva_privilegios(self):
        self.api.force_authenticate(user=self.config)
        resposta = self.api.post("/api/auth/operadores/", {
            "nome": "Joana", "sobrenome": "Almeida", "cargo": "Analista de dados",
            "email": "joana-sggd@exemplo.com", "senha": "SenhaForte@2030!",
            "papel": "Registrador",
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        conta = get_user_model().objects.get(email="joana-sggd@exemplo.com")
        self.assertEqual(conta.get_full_name(), "Joana Almeida")
        self.assertEqual(conta.cargo, "Analista de dados")
        self.assertFalse(conta.is_staff)
        self.assertFalse(conta.is_superuser)
