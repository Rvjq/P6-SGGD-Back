"""Testes do fluxo de Coleta, sem dependência de dados externos."""
from datetime import date
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador


class ColetaAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.config = Usuario.objects.create_user(username="cfg-col", email="cfgcol@exemplo.com", password="senha")
        cls.reg = Usuario.objects.create_user(username="reg-col", email="regcol@exemplo.com", password="senha")
        cls.outro = Usuario.objects.create_user(username="outro-col", email="outrocol@exemplo.com", password="senha")
        cls.hom = Usuario.objects.create_user(username="hom-col", email="homcol@exemplo.com", password="senha")
        cls.duplo = Usuario.objects.create_user(username="duplo-col", email="duplocol@exemplo.com", password="senha")
        cls.cons = Usuario.objects.create_user(username="cons-col", email="conscol@exemplo.com", password="senha")
        for usuario, papeis in (
            (cls.config, ("Configurador",)), (cls.reg, ("Registrador",)),
            (cls.outro, ("Registrador",)), (cls.hom, ("Homologador",)),
            (cls.duplo, ("Registrador", "Homologador")), (cls.cons, ("Consultador",)),
        ):
            usuario.groups.add(*Group.objects.filter(name__in=papeis))
        Distrito = apps.get_model("cadastro", "Distrito")
        TipoUnidade = apps.get_model("cadastro", "TipoUnidade")
        CategoriaAvaliacao = apps.get_model("cadastro", "CategoriaAvaliacao")
        VersaoNormativa = apps.get_model("normativa", "VersaoNormativa")
        Indicador = apps.get_model("normativa", "Indicador")
        RegraIndicador = apps.get_model("normativa", "RegraIndicador")
        cls.cat_usf = CategoriaAvaliacao.objects.get(codigo="USF")
        cls.cat_gg = CategoriaAvaliacao.objects.get(codigo="GG")
        cls.distrito = Distrito.objects.get(codigo="I")
        cls.distrito_2 = Distrito.objects.get(codigo="II")
        cls.usf = TipoUnidade.objects.get(codigo="USF")
        cls.unidade = apps.get_model("cadastro", "Unidade").objects.create(
            codigo="USF-T-01", nome="USF T", tipo=cls.usf, distrito=cls.distrito
        )
        cls.outra_unidade = apps.get_model("cadastro", "Unidade").objects.create(
            codigo="USF-T-02", nome="USF U", tipo=cls.usf, distrito=cls.distrito_2
        )
        cls.versao = VersaoNormativa.objects.create(codigo="TESTE-COLETA", titulo="Teste de coleta")
        cls.indicador = Indicador.objects.create(versao=cls.versao, codigo="1", nome="Medicamentos")
        RegraIndicador.objects.create(indicador=cls.indicador, categoria=cls.cat_usf)
        RegraIndicador.objects.create(indicador=cls.indicador, categoria=cls.cat_gg)
        cls.outra_versao = VersaoNormativa.objects.create(codigo="VERSAO-OUTRA", titulo="Outra")
        cls.outro_indicador = Indicador.objects.create(versao=cls.outra_versao, codigo="1", nome="Outro")
        cls.competencia = CompetenciaColeta.objects.create(mes=date(2026, 9, 1), versao=cls.versao)
        cls.autorizacao = AutorizacaoColeta.objects.create(usuario=cls.reg, unidade=cls.unidade)
        AutorizacaoColeta.objects.create(usuario=cls.duplo, unidade=cls.unidade)

    def setUp(self):
        self.api = APIClient()

    def logar(self, user):
        self.api.force_authenticate(user=user)

    def dados_registro(self, **extra):
        base = {
            "competencia": self.competencia.id,
            "indicador": self.indicador.id,
            "categoria": self.cat_usf.id,
            "unidade": self.unidade.id,
            "dados": {"numerador": 18, "denominador": 20},
            "fonte": "Sistema Hórus / teste",
        }
        base.update(extra)
        return base

    def criar_por(self, usuario=None, **extra):
        self.logar(usuario or self.reg)
        return self.api.post("/api/coleta/registros/", self.dados_registro(**extra), format="json")

    def enviar(self, id, user=None):
        self.logar(user or self.reg)
        return self.api.post(f"/api/coleta/registros/{id}/enviar/", {}, format="json")

    def test_competencia_nao_aceita_dia_qualquer(self):
        with self.assertRaises(ValidationError):
            CompetenciaColeta.objects.create(mes=date(2026, 9, 20), versao=self.versao)

    def test_competencia_nao_muda_versao_ou_mes(self):
        self.competencia.versao = self.outra_versao
        with self.assertRaises(ValidationError):
            self.competencia.save()

    def test_competencia_criacao_exclusiva_configurador(self):
        self.logar(self.reg)
        resposta = self.api.post("/api/coleta/competencias/", {
            "mes": "2026-10-01", "versao": self.versao.pk
        }, format="json")
        self.assertEqual(resposta.status_code, 403)
        self.logar(self.config)
        resposta = self.api.post("/api/coleta/competencias/", {
            "mes": "2026-10-01", "versao": self.versao.pk
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)

    def test_autorizacao_criada_por_configurador(self):
        self.logar(self.reg)
        self.assertEqual(self.api.get("/api/coleta/autorizacoes/").status_code, 403)
        self.logar(self.config)
        resposta = self.api.post("/api/coleta/autorizacoes/", {
            "usuario": self.outro.id, "distrito": self.distrito.id,
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)

    def test_sem_login_nao_acessa_coleta(self):
        self.assertIn(self.api.get("/api/coleta/registros/").status_code, (401, 403))

    def test_registrador_precisa_de_autorizacao_de_escopo(self):
        resposta = self.criar_por(self.outro)
        self.assertEqual(resposta.status_code, 403)

    def test_autorizacao_distrito_inclui_unidades_subordinadas(self):
        AutorizacaoColeta.objects.create(usuario=self.outro, distrito=self.distrito)
        resposta = self.criar_por(self.outro)
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(self.criar_por(self.outro, unidade=self.outra_unidade.id).status_code, 403)
        # A autorização distrital não se estende a unidades de outros distritos.

    def test_cadastro_valido_cria_rascunho_com_autor_real(self):
        resp = self.criar_por()
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = RegistroIndicador.objects.get(pk=resp.data["id"])
        self.assertEqual(obj.registrado_por_id, self.reg.id)
        self.assertEqual(obj.situacao, "RASCUNHO")

    def test_indicador_de_outra_versao_e_rejeitado(self):
        resp = self.criar_por(indicador=self.outro_indicador.pk)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_categoria_nao_aplicavel_e_rejeitada(self):
        resp = self.criar_por(categoria=self.cat_gg.pk)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_dados_vazios_e_rejeitado(self):
        resp = self.criar_por(dados={})
        self.assertEqual(resp.status_code, 400)

    def test_registro_duplicado_e_rejeitado(self):
        self.assertEqual(self.criar_por().status_code, 201)
        self.assertEqual(self.criar_por().status_code, 400)

    def test_registrador_nao_ve_outro_registro(self):
        resp = self.criar_por()
        id = resp.data["id"]
        self.logar(self.outro)
        resposta_lista = self.api.get("/api/coleta/registros/")
        quantidade = resposta_lista.data.get("count", 0) if isinstance(resposta_lista.data, dict) else len(resposta_lista.data)
        self.assertEqual(quantidade, 0)
        self.assertEqual(self.api.get(f"/api/coleta/registros/{id}/").status_code, 404)

    def test_consultador_nao_acessa_registros_sem_escopo(self):
        self.logar(self.cons)
        self.assertEqual(self.api.get("/api/coleta/registros/").status_code, 403)

    def test_envio_e_homologacao(self):
        resp = self.criar_por()
        id = resp.data["id"]
        self.assertEqual(self.enviar(id).status_code, 200)
        self.logar(self.hom)
        resp = self.api.post(f"/api/coleta/registros/{id}/homologar/", {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["situacao"], "HOMOLOGADO")
        self.logar(self.reg)
        self.assertEqual(self.api.patch(f"/api/coleta/registros/{id}/", {"fonte": "Alterada"}, format="json").status_code, 400)

    def test_devolucao_e_correcao(self):
        resp = self.criar_por()
        id = resp.data["id"]
        self.enviar(id)
        self.logar(self.hom)
        self.assertEqual(self.api.post(f"/api/coleta/registros/{id}/devolver/", {}, format="json").status_code, 400)
        resp = self.api.post(f"/api/coleta/registros/{id}/devolver/", {"motivo": "Conferir fonte"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.logar(self.reg)
        resp = self.api.patch(f"/api/coleta/registros/{id}/", {"dados": {"numerador": 20, "denominador": 20}}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["situacao"], "RASCUNHO")
        self.assertEqual(self.enviar(id).status_code, 200)

    def test_registrador_nao_pode_homologar(self):
        id = self.criar_por().data["id"]
        self.enviar(id)
        self.logar(self.reg)
        self.assertEqual(self.api.post(f"/api/coleta/registros/{id}/homologar/", {}, format="json").status_code, 403)

    def test_mesmo_usuario_com_ambos_papeis_nao_homologa_proprio(self):
        id = self.criar_por(self.duplo).data["id"]
        self.enviar(id, self.duplo)
        self.logar(self.duplo)
        self.assertEqual(self.api.post(f"/api/coleta/registros/{id}/homologar/", {}, format="json").status_code, 403)

    def test_competencia_nao_fecha_com_registros_pendentes(self):
        self.criar_por()
        self.logar(self.config)
        resp = self.api.patch(f"/api/coleta/competencias/{self.competencia.id}/", {"estado": "FECHADA"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_registro_de_distrito(self):
        AutorizacaoColeta.objects.create(usuario=self.reg, distrito=self.distrito)
        resp = self.criar_por(categoria=self.cat_gg.pk, unidade=None, distrito=self.distrito.pk)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_autorizacao_com_ambos_escopos_e_rejeitada(self):
        with self.assertRaises(ValidationError):
            AutorizacaoColeta.objects.create(
                usuario=self.reg, unidade=self.unidade, distrito=self.distrito
            )

    def test_competencia_fechada_bloqueia_novo_registro(self):
        self.competencia.estado = CompetenciaColeta.Estado.FECHADA
        self.competencia.save()
        self.assertEqual(self.criar_por().status_code, 400)

    def test_competencia_fechada_nao_reabre(self):
        self.competencia.estado = CompetenciaColeta.Estado.FECHADA
        self.competencia.save()
        self.logar(self.config)
        resposta = self.api.patch(
            f"/api/coleta/competencias/{self.competencia.pk}/",
            {"estado": "ABERTA"}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)

    def test_homologador_nao_ve_rascunhos_de_terceiros(self):
        id = self.criar_por().data["id"]
        self.logar(self.hom)
        self.assertEqual(self.api.get(f"/api/coleta/registros/{id}/").status_code, 404)

    def test_alteracao_de_destino_apos_criacao_e_bloqueada(self):
        id = self.criar_por().data["id"]
        self.logar(self.reg)
        resposta = self.api.patch(
            f"/api/coleta/registros/{id}/",
            {"unidade": self.outra_unidade.id}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)


    def test_opcoes_restritas_ao_registrador_e_a_competencia(self):
        self.logar(self.reg)
        resposta = self.api.get(f"/api/coleta/opcoes/?competencia={self.competencia.pk}")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        escopos = resposta.data["escopos"]
        self.assertEqual(len(escopos), 1)
        self.assertEqual(escopos[0]["id"], self.unidade.pk)
        self.assertEqual(escopos[0]["categoria"], self.cat_usf.pk)
        self.assertTrue(any(x["id"] == self.indicador.pk for x in resposta.data["indicadores"]))
        self.assertFalse(any(x["id"] == self.outro_indicador.pk for x in resposta.data["indicadores"]))
        self.logar(self.cons)
        self.assertEqual(self.api.get(f"/api/coleta/opcoes/?competencia={self.competencia.pk}").status_code, 403)

    def test_opcoes_distritais_mostram_unidades_e_categorias_do_distrito(self):
        AutorizacaoColeta.objects.create(usuario=self.outro, distrito=self.distrito)
        self.logar(self.outro)
        resposta = self.api.get(f"/api/coleta/opcoes/?competencia={self.competencia.pk}")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        escopos = resposta.data["escopos"]
        self.assertTrue(any(x["tipo"] == "UNIDADE" and x["id"] == self.unidade.pk for x in escopos))
        self.assertFalse(any(x["tipo"] == "UNIDADE" and x["id"] == self.outra_unidade.pk for x in escopos))
        self.assertTrue(any(x["tipo"] == "DISTRITO" and x["categoria_codigo"] == "GG" for x in escopos))

    def test_resposta_registro_inclui_rotulos_somente_leitura(self):
        resposta = self.criar_por()
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["indicador_nome"], "Medicamentos")
        self.assertEqual(resposta.data["unidade_nome"], self.unidade.nome)
        self.assertEqual(resposta.data["registrado_por_email"], self.reg.email)
