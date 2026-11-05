"""Testes de identidade, autenticação e autorização do componente acesso."""

import json

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from .interface import ExigePermissao, usuario_tem_permissao
from .models import Usuario


SENHA_TESTE = "Senha-de-teste-123"
PERMISSAO_TESTE = "acesso.view_usuario"

# Contrato esperado, independente de como a migração concede as permissões.
PERMISSOES_POR_PAPEL = {
    "Configurador": {
        "cadastrar_indicador",
        "cadastrar_meta",
        "configurar_regra_calculo",
        "gerenciar_competencia",
        "cadastrar_unidade",
        "cadastrar_avaliado",
    },
    "Registrador": {"registrar_resultado"},
    "Homologador": {"homologar_resultado"},
    "Consultador": {"consultar_resultados", "apresentar_recurso"},
}

# As operações abaixo já constam do catálogo, mas não têm titular definido.
PERMISSOES_SEM_PAPEL = {
    "encerrar_ciclo",
    "publicar_resultado",
    "julgar_recurso",
    "enviar_resultado_folha",
}

TODAS_OPERACOES = (
    set().union(*PERMISSOES_POR_PAPEL.values()) | PERMISSOES_SEM_PAPEL
)


class AcessoTestMixin:
    """Criação centralizada de usuários/grupos para todos os testes."""

    def criar_usuario(self, username="ana", *, papeis=(), superusuario=False):
        criador = (
            Usuario.objects.create_superuser
            if superusuario
            else Usuario.objects.create_user
        )
        usuario = criador(
            username=username,
            email=f"{username}@exemplo.com",
            password=SENHA_TESTE,
        )
        usuario.groups.add(*(Group.objects.get(name=nome) for nome in papeis))
        return usuario

    def criar_grupo(self, nome, *permissoes):
        grupo = Group.objects.create(name=nome)
        for codigo in permissoes:
            app_label, codename = codigo.split(".", 1)
            grupo.permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        return grupo

    def requisitar(self, view, usuario=None):
        request = APIRequestFactory().post("/operacao/")
        if usuario is not None:
            force_authenticate(request, user=usuario)
        return view.as_view()(request)


class ModeloUsuarioTests(AcessoTestMixin, TestCase):
    def test_modelo_customizado_e_utilizado(self):
        self.assertIs(get_user_model(), Usuario)

    def test_usuario_tem_email_e_senha_com_hash(self):
        usuario = self.criar_usuario()
        self.assertEqual(usuario.email, "ana@exemplo.com")
        self.assertNotEqual(usuario.password, SENHA_TESTE)
        self.assertTrue(usuario.check_password(SENHA_TESTE))

    def test_banco_rejeita_email_vazio(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Usuario.objects.create_user(
                    username="sememail",
                    email="",
                    password=SENHA_TESTE,
                )

    def test_banco_rejeita_email_duplicado_sem_diferenciar_caixa(self):
        self.criar_usuario()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Usuario.objects.create_user(
                    username="bia",
                    email="ANA@EXEMPLO.COM",
                    password=SENHA_TESTE,
                )


class ConfiguracaoPapeisTests(TestCase):
    def test_apenas_papeis_previstos_estao_cadastrados(self):
        encontrados = set(Group.objects.values_list("name", flat=True))
        self.assertEqual(encontrados, set(PERMISSOES_POR_PAPEL))

    def test_cada_papel_possui_exatamente_suas_permissoes(self):
        for nome, esperadas in PERMISSOES_POR_PAPEL.items():
            with self.subTest(papel=nome):
                grupo = Group.objects.get(name=nome)
                obtidas = set(grupo.permissions.values_list("codename", flat=True))
                self.assertEqual(obtidas, esperadas)

    def test_catalogo_de_operacoes_contem_somente_as_previstas(self):
        catalogo = set(
            Permission.objects.filter(
                content_type__app_label="acesso",
                content_type__model="operacao",
            ).values_list("codename", flat=True)
        )
        self.assertEqual(catalogo, TODAS_OPERACOES)


class AutorizacaoTests(AcessoTestMixin, TestCase):
    def test_cada_papel_autoriza_somente_suas_operacoes(self):
        for indice, (papel, permitidas) in enumerate(PERMISSOES_POR_PAPEL.items()):
            usuario = self.criar_usuario(f"usuario{indice}", papeis=(papel,))
            for operacao in sorted(TODAS_OPERACOES):
                with self.subTest(papel=papel, operacao=operacao):
                    self.assertEqual(
                        usuario_tem_permissao(usuario, f"acesso.{operacao}"),
                        operacao in permitidas,
                    )

    def test_multiplos_papeis_acumulam_permissoes(self):
        usuario = self.criar_usuario(papeis=("Registrador", "Consultador"))
        self.assertTrue(usuario_tem_permissao(usuario, "acesso.registrar_resultado"))
        self.assertTrue(usuario_tem_permissao(usuario, "acesso.consultar_resultados"))
        self.assertFalse(usuario_tem_permissao(usuario, "acesso.homologar_resultado"))

    def test_usuario_sem_papel_nao_pode_executar_operacoes(self):
        usuario = self.criar_usuario()
        for operacao in sorted(TODAS_OPERACOES):
            with self.subTest(operacao=operacao):
                self.assertFalse(usuario_tem_permissao(usuario, f"acesso.{operacao}"))

    def test_permissao_direta_do_usuario_e_reconhecida(self):
        usuario = self.criar_usuario()
        permissao = Permission.objects.get(
            content_type__app_label="acesso", codename="view_usuario"
        )
        usuario.user_permissions.add(permissao)
        self.assertTrue(usuario_tem_permissao(usuario, PERMISSAO_TESTE))

    def test_usuario_inativo_nao_tem_acesso(self):
        usuario = self.criar_usuario(papeis=("Registrador",))
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        self.assertFalse(usuario_tem_permissao(usuario, "acesso.registrar_resultado"))

    def test_usuario_anonimo_nao_tem_acesso(self):
        for usuario in (None, AnonymousUser()):
            with self.subTest(usuario=usuario):
                self.assertFalse(usuario_tem_permissao(usuario, PERMISSAO_TESTE))

    def test_superusuario_ativo_tem_permissao(self):
        usuario = self.criar_usuario("admin", superusuario=True)
        self.assertTrue(usuario_tem_permissao(usuario, PERMISSAO_TESTE))


class AutenticacaoEmailTests(AcessoTestMixin, TestCase):
    def test_autentica_com_email_e_senha_corretos(self):
        usuario = self.criar_usuario()
        autenticado = authenticate(email="ana@exemplo.com", password=SENHA_TESTE)
        self.assertEqual(autenticado, usuario)

    def test_email_nao_diferencia_maiusculas(self):
        usuario = self.criar_usuario()
        autenticado = authenticate(email="ANA@EXEMPLO.COM", password=SENHA_TESTE)
        self.assertEqual(autenticado, usuario)

    def test_rejeita_senha_incorreta(self):
        self.criar_usuario()
        autenticado = authenticate(email="ana@exemplo.com", password="senha-errada")
        self.assertIsNone(autenticado)

    def test_rejeita_usuario_inativo(self):
        usuario = self.criar_usuario()
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        autenticado = authenticate(email="ana@exemplo.com", password=SENHA_TESTE)
        self.assertIsNone(autenticado)

    def test_rejeita_email_inexistente(self):
        autenticado = authenticate(email="inexistente@exemplo.com", password=SENHA_TESTE)
        self.assertIsNone(autenticado)


class OperacaoProtegida(APIView):
    permission_classes = [ExigePermissao]
    permissoes_exigidas = (PERMISSAO_TESTE,)

    def post(self, request):
        return Response({"ok": True})


class OperacaoComDuasPermissoes(OperacaoProtegida):
    permissoes_exigidas = ("acesso.view_usuario", "acesso.change_usuario")


class OperacaoSemPermissoes(OperacaoProtegida):
    permissoes_exigidas = ()


class JulgarRecurso(OperacaoProtegida):
    permissoes_exigidas = ("acesso.julgar_recurso",)


class PermissoesApiTests(AcessoTestMixin, TestCase):
    def test_requisicao_anonima_e_negada(self):
        resposta = self.requisitar(OperacaoProtegida)
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resposta.data["detail"].code, "not_authenticated")

    def test_usuario_sem_permissao_recebe_403(self):
        resposta = self.requisitar(OperacaoProtegida, self.criar_usuario())
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resposta.data["detail"].code, "permission_denied")

    def test_usuario_com_permissao_consegue_executar(self):
        usuario = self.criar_usuario()
        usuario.groups.add(self.criar_grupo("Leitura de usuários", PERMISSAO_TESTE))
        resposta = self.requisitar(OperacaoProtegida, usuario)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

    def test_view_exige_todas_as_permissoes_declaradas(self):
        usuario = self.criar_usuario()
        usuario.groups.add(self.criar_grupo("Apenas leitura", PERMISSAO_TESTE))
        resposta = self.requisitar(OperacaoComDuasPermissoes, usuario)
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_view_sem_permissoes_declaradas_falha(self):
        with self.assertRaises(ImproperlyConfigured):
            self.requisitar(OperacaoSemPermissoes, self.criar_usuario())

    def test_julgamento_de_recurso_nao_e_atribuido_automaticamente(self):
        for indice, papel in enumerate(PERMISSOES_POR_PAPEL):
            with self.subTest(papel=papel):
                usuario = self.criar_usuario(f"usuario{indice}", papeis=(papel,))
                resposta = self.requisitar(JulgarRecurso, usuario)
                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)


class LoginAPITests(AcessoTestMixin, TestCase):
    def setUp(self):
        self.usuario = self.criar_usuario()
        self.client = Client(enforce_csrf_checks=True)
        resposta = self.client.get(reverse("csrf"))
        self.csrf_token = resposta.cookies["csrftoken"].value

    def fazer_login(self, email, senha, *, csrf=True):
        headers = {}
        if csrf:
            headers["HTTP_X_CSRFTOKEN"] = self.csrf_token

        return self.client.post(
            reverse("login"),
            data=json.dumps({"email": email, "password": senha}),
            content_type="application/json",
            **headers,
        )

    def test_login_com_credenciais_validas(self):
        resposta = self.fazer_login("ana@exemplo.com", SENHA_TESTE)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["email"], self.usuario.email)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.usuario.pk)

    def test_login_com_senha_incorreta(self):
        resposta = self.fazer_login("ana@exemplo.com", "senha-incorreta")
        self.assertEqual(resposta.status_code, 401)

    def test_login_sem_csrf(self):
        resposta = self.fazer_login("ana@exemplo.com", SENHA_TESTE, csrf=False)
        self.assertEqual(resposta.status_code, 403)

    def test_me_sem_autenticacao(self):
        resposta = self.client.get(reverse("me"))
        self.assertEqual(resposta.status_code, 401)

    def test_me_retorna_usuario_autenticado(self):
        self.usuario.groups.add(Group.objects.get(name="Registrador"))
        self.fazer_login("ana@exemplo.com", SENHA_TESTE)
        resposta = self.client.get(reverse("me"))
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["email"], self.usuario.email)
        self.assertIn("Registrador", dados["papeis"])
        self.assertIn("acesso.registrar_resultado", dados["permissoes"])

    def test_me_distingue_superusuario_de_papel_funcional(self):
        admin = self.criar_usuario("admin", superusuario=True)
        self.client.force_login(admin)
        resposta = self.client.get(reverse("me"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["is_superuser"])
        self.assertEqual(resposta.json()["papeis"], [])

    def test_me_usuario_comum_nao_e_superusuario(self):
        self.fazer_login("ana@exemplo.com", SENHA_TESTE)
        resposta = self.client.get(reverse("me"))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json()["is_superuser"])

    def test_logout_encerra_sessao(self):
        self.fazer_login("ana@exemplo.com", SENHA_TESTE)
        token = self.client.cookies["csrftoken"].value
        resposta = self.client.post(reverse("logout"), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(resposta.status_code, 200)
        resposta_me = self.client.get(reverse("me"))
        self.assertEqual(resposta_me.status_code, 401)

    def test_logout_sem_csrf(self):
        self.fazer_login("ana@exemplo.com", SENHA_TESTE)
        resposta = self.client.post(reverse("logout"))
        self.assertEqual(resposta.status_code, 403)
        resposta_me = self.client.get(reverse("me"))
        self.assertEqual(resposta_me.status_code, 200)
