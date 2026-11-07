"""Testes de cadastro: categorias CAM 1.2, vínculos, vigência e API."""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from .interface import responsabilidades_na_data
from .models import (
    CategoriaAvaliacao,
    Distrito,
    PessoaAvaliada,
    Responsabilidade,
    TipoUnidade,
    Unidade,
)


class CadastroEstruturalTests(TestCase):
    def setUp(self):
        self.distrito = Distrito.objects.get(codigo="I")
        self.tipo = TipoUnidade.objects.get(codigo="USF")
        self.cat_usf = CategoriaAvaliacao.objects.get(codigo="USF")
        self.cat_gg = CategoriaAvaliacao.objects.get(codigo="GG")
        self.usf_a = Unidade.objects.create(
            codigo="USF-A", nome="USF A (teste)", tipo=self.tipo, distrito=self.distrito
        )
        self.usf_b = Unidade.objects.create(
            codigo="USF-B", nome="USF B (teste)", tipo=self.tipo, distrito=self.distrito
        )
        self.ana = PessoaAvaliada.objects.create(codigo="AV-1", nome="Ana (teste)")

    def test_semente_cam_12_com_11_categorias_e_8_distritos(self):
        self.assertEqual(CategoriaAvaliacao.objects.count(), 11)
        self.assertEqual(CategoriaAvaliacao.objects.filter(escopo="UNIDADE").count(), 7)
        self.assertEqual(CategoriaAvaliacao.objects.filter(escopo="DISTRITO").count(), 4)
        self.assertEqual(TipoUnidade.objects.count(), 7)
        self.assertEqual(Distrito.objects.count(), 8)

    def test_gestor_de_duas_unidades(self):
        for unidade in (self.usf_a, self.usf_b):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_usf,
                unidade=unidade, data_inicio=date(2026, 9, 1),
            )
        self.assertEqual(self.ana.responsabilidades.count(), 2)

    def test_consulta_de_vinculo_por_data(self):
        Responsabilidade.objects.create(
            pessoa=self.ana, categoria=self.cat_usf, unidade=self.usf_a,
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 9, 30),
        )
        self.assertEqual(responsabilidades_na_data(self.ana.pk, date(2026, 9, 1)).count(), 1)
        self.assertEqual(responsabilidades_na_data(self.ana.pk, date(2026, 10, 1)).count(), 0)

    def test_gerente_distrital_sem_vinculo_manual_as_unidades(self):
        vinculo = Responsabilidade.objects.create(
            pessoa=self.ana, categoria=self.cat_gg,
            distrito=self.distrito, data_inicio=date(2026, 9, 1),
        )
        self.assertIsNone(vinculo.unidade_id)
        self.assertEqual(vinculo.distrito.unidades.count(), 2)

    def test_categoria_distrital_nao_aceita_unidade(self):
        with self.assertRaises(ValidationError):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_gg,
                unidade=self.usf_a, data_inicio=date(2026, 9, 1),
            )

    def test_categoria_unidade_nao_aceita_distrito(self):
        with self.assertRaises(ValidationError):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_usf,
                distrito=self.distrito, data_inicio=date(2026, 9, 1),
            )

    def test_responsabilidade_exige_um_unico_destino(self):
        with self.assertRaises(ValidationError):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_usf,
                unidade=self.usf_a, distrito=self.distrito,
                data_inicio=date(2026, 9, 1),
            )
        with self.assertRaises(ValidationError):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_usf,
                data_inicio=date(2026, 9, 1),
            )

    def test_data_fim_nao_pode_anteceder_inicio(self):
        with self.assertRaises(ValidationError):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_usf, unidade=self.usf_a,
                data_inicio=date(2026, 9, 1), data_fim=date(2026, 8, 31),
            )

    def test_periodos_sobrepostos_na_mesma_unidade_sao_rejeitados(self):
        Responsabilidade.objects.create(
            pessoa=self.ana, categoria=self.cat_usf, unidade=self.usf_a,
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 9, 30),
        )
        with self.assertRaises(ValidationError):
            Responsabilidade.objects.create(
                pessoa=self.ana, categoria=self.cat_usf, unidade=self.usf_a,
                data_inicio=date(2026, 9, 1),
            )

    def test_periodos_consecutivos_na_mesma_unidade_sao_aceitos(self):
        Responsabilidade.objects.create(
            pessoa=self.ana, categoria=self.cat_usf, unidade=self.usf_a,
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 9, 30),
        )
        Responsabilidade.objects.create(
            pessoa=self.ana, categoria=self.cat_usf, unidade=self.usf_a,
            data_inicio=date(2026, 10, 1),
        )
        self.assertEqual(self.ana.responsabilidades.count(), 2)

    def test_tipo_unidade_nao_aponta_para_cargo_distrital(self):
        with self.assertRaises(ValidationError):
            TipoUnidade.objects.create(
                codigo="INVALIDO", nome="Inválido", categoria=self.cat_gg
            )

    def test_historico_protegido_contra_exclusao(self):
        Responsabilidade.objects.create(
            pessoa=self.ana, categoria=self.cat_usf,
            unidade=self.usf_a, data_inicio=date(2026, 9, 1),
        )
        with self.assertRaises(ProtectedError):
            self.ana.delete()
        with self.assertRaises(ProtectedError):
            self.usf_a.delete()

    def test_usuario_login_e_opcional_na_pessoa(self):
        self.assertIsNone(self.ana.usuario)
        usuario = get_user_model().objects.create_user(
            username="avaliada", email="avaliada@exemplo.com", password="segredo-ficticio"
        )
        self.ana.usuario = usuario
        self.ana.save()
        self.assertEqual(usuario.pessoa_avaliada, self.ana)


class CadastroAPITests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.configurador = Usuario.objects.create_user(
            username="config-api", email="config-api@exemplo.com", password="senha-teste"
        )
        self.configurador.groups.add(Group.objects.get(name="Configurador"))
        self.registrador = Usuario.objects.create_user(
            username="reg-api", email="reg-api@exemplo.com", password="senha-teste"
        )
        self.registrador.groups.add(Group.objects.get(name="Registrador"))
        self.api = APIClient()

    def test_sem_login_nao_pode_listar(self):
        resposta = self.api.get("/api/cadastro/distritos/")
        self.assertIn(resposta.status_code, (401, 403))

    def test_registrador_nao_pode_cadastrar_nem_listar_todos_os_avaliados(self):
        self.api.force_authenticate(user=self.registrador)
        self.assertEqual(self.api.get("/api/cadastro/avaliados/").status_code, 403)
        self.assertEqual(
            self.api.post(
                "/api/cadastro/unidades/", {"codigo": "X", "nome": "X", "tipo": 1, "distrito": 1},
                format="json",
            ).status_code,
            403,
        )

    def test_configurador_lista_categorias_cam_12(self):
        self.api.force_authenticate(user=self.configurador)
        resposta = self.api.get("/api/cadastro/categorias-avaliacao/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.data), 11)

    def test_configurador_cadastra_unidade_e_avaliado(self):
        self.api.force_authenticate(user=self.configurador)
        tipo = TipoUnidade.objects.get(codigo="USF")
        distrito = Distrito.objects.get(codigo="I")
        resposta = self.api.post(
            "/api/cadastro/unidades/",
            {"codigo": "USF-X", "nome": "USF X (teste)", "tipo": tipo.pk, "distrito": distrito.pk},
            format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)
        resposta = self.api.post(
            "/api/cadastro/avaliados/",
            {"codigo": "AV-99", "nome": "Pessoa de Teste"}, format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)

    def test_configurador_cria_responsabilidade_e_rejeita_escopo_invalido(self):
        self.api.force_authenticate(user=self.configurador)
        pessoa = PessoaAvaliada.objects.create(codigo="AV-99", nome="Pessoa de Teste")
        distrito = Distrito.objects.get(codigo="I")
        categoria = CategoriaAvaliacao.objects.get(codigo="GG")
        resposta = self.api.post(
            "/api/cadastro/responsabilidades/",
            {"pessoa": pessoa.pk, "categoria": categoria.pk,
             "distrito": distrito.pk, "data_inicio": "2026-09-01"},
            format="json",
        )
        self.assertEqual(resposta.status_code, 201, resposta.data)
        tipo = TipoUnidade.objects.get(codigo="USF")
        unidade = Unidade.objects.create(
            codigo="USF-9", nome="USF Nove", tipo=tipo, distrito=distrito
        )
        resposta = self.api.post(
            "/api/cadastro/responsabilidades/",
            {"pessoa": pessoa.pk, "categoria": categoria.pk,
             "unidade": unidade.pk, "data_inicio": "2026-09-01"},
            format="json",
        )
        self.assertEqual(resposta.status_code, 400)

    def test_nao_permite_excluir_cadastros_pela_api(self):
        self.api.force_authenticate(user=self.configurador)
        distrito = Distrito.objects.get(codigo="I")
        resposta = self.api.delete(f"/api/cadastro/distritos/{distrito.pk}/")
        self.assertEqual(resposta.status_code, 405)

    def test_categorias_sao_somente_leitura_na_api(self):
        self.api.force_authenticate(user=self.configurador)
        resposta = self.api.post(
            "/api/cadastro/categorias-avaliacao/",
            {"codigo": "TESTE", "nome": "Teste", "escopo": "UNIDADE"},
            format="json",
        )
        self.assertEqual(resposta.status_code, 405)
