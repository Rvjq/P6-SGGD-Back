"""Regressão: I5 distrital segue as pessoas avaliadas e os pesos CAM 1.2.

A categoria GG é usada apenas como a referência técnica única para o dado I5.
Sem gestor elegível não há formulário distrital, sem excluir registros passados.
"""
from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador


class IndicadorCincoDistritalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("importar_cam12", verbosity=0)
        call_command("configurar_regras_cam12", verbosity=0)
        Usuario = get_user_model()
        cls.registrador = Usuario.objects.create_user(
            username="distrito-i5-reg", email="i5-reg@exemplo.com", password="x",
        )
        cls.registrador.groups.add(Group.objects.get(name="Registrador"))
        cls.configurador = Usuario.objects.create_user(
            username="distrito-i5-conf", email="i5-cfg@exemplo.com", password="x",
        )
        cls.configurador.groups.add(Group.objects.get(name="Configurador"))
        cls.distrito = apps.get_model("cadastro", "Distrito").objects.get(codigo="I")
        cls.categorias = {
            c.codigo: c for c in apps.get_model("cadastro", "CategoriaAvaliacao").objects.filter(
                escopo="DISTRITO"
            )
        }
        cls.versao = apps.get_model("normativa", "VersaoNormativa").objects.get(codigo="CAM 1.2")
        cls.i5 = apps.get_model("normativa", "Indicador").objects.get(
            codigo="5", versao=cls.versao
        )
        cls.novembro = CompetenciaColeta.objects.create(
            mes=date(2026, 11, 1), versao=cls.versao,
        )
        cls.dezembro = CompetenciaColeta.objects.create(
            mes=date(2026, 12, 1), versao=cls.versao,
        )
        AutorizacaoColeta.objects.create(usuario=cls.registrador, distrito=cls.distrito)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=self.registrador)

    def designar(self, categoria, *, inicio=date(2026, 1, 1), fim=None, ativa=True):
        Pessoa = apps.get_model("cadastro", "PessoaAvaliada")
        Responsabilidade = apps.get_model("cadastro", "Responsabilidade")
        pessoa = Pessoa.objects.create(
            codigo=f"I5-TEST-{Pessoa.objects.count()+1}",
            nome=f"Pessoa {categoria}", ativa=ativa,
        )
        Responsabilidade.objects.create(
            pessoa=pessoa, distrito=self.distrito,
            categoria=self.categorias[categoria], data_inicio=inicio, data_fim=fim,
        )
        return pessoa

    def distrito_planejado(self, competencia=None):
        periodo = competencia or self.novembro
        resposta = self.api.get(f"/api/coleta/tarefas/?competencia={periodo.pk}")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        distritos = [e for e in resposta.data["escopos"] if e["tipo"] == "DISTRITO"]
        self.assertEqual(len(distritos), 1)
        return distritos[0]

    def test_sem_pessoa_distrital_e_pendencia_administrativa_nao_i5(self):
        escopo = self.distrito_planejado()
        self.assertEqual(escopo["estado_configuracao"], "SEM_RESPONSAVEL")
        self.assertEqual(escopo["tarefas"], [])
        self.assertIn("Defina", escopo["aviso"])
        self.assertEqual(escopo["responsaveis"], [])
        salvar = self.api.post('/api/coleta/tarefas/salvar/', {
            "competencia": self.novembro.pk, "unidade": None,
            "distrito": self.distrito.pk, "indicador": self.i5.pk,
            "itens": [{"codigo":"5.I", "dados":{"valor":88}, "fonte":"SIM"}],
        }, format='json')
        self.assertEqual(salvar.status_code, 403)
        self.assertFalse(RegistroIndicador.objects.exists())

    def test_somente_snb2_nao_gera_i5(self):
        self.designar("SNB2")
        escopo = self.distrito_planejado()
        self.assertEqual(escopo["estado_configuracao"], "SEM_I5_APLICAVEL")
        self.assertEqual(escopo["tarefas"], [])
        self.assertEqual(escopo["responsaveis"][0]["categoria"], "SNB2")
        self.assertEqual(
            escopo["responsaveis"][0]["categoria_nome"], self.categorias["SNB2"].nome
        )

    def test_gg_sna_snb1_exigem_i5_uma_unica_vez(self):
        for categoria in ("GG", "SNA", "SNB1", "SNB2"):
            self.designar(categoria)
        escopo = self.distrito_planejado()
        self.assertEqual(escopo["estado_configuracao"], "CONFIGURADO")
        self.assertEqual([t["codigo"] for t in escopo["tarefas"]], ["5"])
        self.assertEqual(len(escopo["responsaveis"]), 4)
        self.assertEqual(escopo["tarefas"][0]["categoria_codigo"], "GG")
        self.assertFalse(RegistroIndicador.objects.exists())
        # Uma única coleta técnica para os vários gestores elegíveis.
        resposta = self.api.post('/api/coleta/tarefas/salvar/', {
            "competencia": self.novembro.pk, "unidade": None,
            "distrito": self.distrito.pk, "indicador": self.i5.pk,
            "itens": [{"codigo":"5.I", "dados":{"valor":88}, "fonte":"SIM"}],
        }, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(RegistroIndicador.objects.count(), 1)
        self.assertEqual(RegistroIndicador.objects.get().categoria.codigo, "GG")
        self.assertEqual(len(self.distrito_planejado()["tarefas"]), 1)

    def test_sna_sozinha_exige_i5(self):
        self.designar("SNA")
        self.assertEqual([t["codigo"] for t in self.distrito_planejado()["tarefas"]], ["5"])

    def test_snb1_sozinha_exige_i5(self):
        self.designar("SNB1")
        self.assertEqual([t["codigo"] for t in self.distrito_planejado()["tarefas"]], ["5"])

    def test_vigencia_de_responsabilidade_depende_do_mes(self):
        self.designar("GG", inicio=date(2026, 12, 1))
        self.assertEqual(self.distrito_planejado()["estado_configuracao"], "SEM_RESPONSAVEL")
        self.assertEqual(self.distrito_planejado(self.dezembro)["estado_configuracao"], "CONFIGURADO")

    def test_responsavel_inativo_ou_designacao_expirada_nao_gera(self):
        self.designar("GG", ativa=False)
        self.designar("SNA", fim=date(2026, 10, 31))
        self.assertEqual(self.distrito_planejado()["estado_configuracao"], "SEM_RESPONSAVEL")

    def test_catalogo_exibe_nome_da_categoria_distrital(self):
        self.designar("SNB2")
        self.api.force_authenticate(user=self.configurador)
        resposta = self.api.get('/api/cadastro/painel/?mes=2026-11')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        distrito = next(d for d in resposta.data['distritos'] if d['id'] == self.distrito.pk)
        self.assertEqual(len(distrito['responsaveis']), 1)
        self.assertEqual(distrito['responsaveis'][0]['categoria_nome'], self.categorias['SNB2'].nome)

    def test_homologacao_exibe_mais_de_um_gestor_com_seu_tipo(self):
        self.designar("GG")
        self.designar("SNB1")
        homologador = get_user_model().objects.create_user(
            username="i5-hom", email="i5-hom@exemplo.com", password="x",
        )
        homologador.groups.add(Group.objects.get(name="Homologador"))
        indicador_folha = apps.get_model("normativa", "Indicador").objects.get(
            codigo="5.I", versao=self.versao,
        )
        RegistroIndicador.objects.create(
            competencia=self.novembro, indicador=indicador_folha,
            categoria=self.categorias["GG"], distrito=self.distrito,
            dados={"valor": 85}, fonte="SIM", situacao="ENVIADO",
            registrado_por=self.registrador, enviado_em=timezone.now(),
        )
        self.api.force_authenticate(user=homologador)
        resp = self.api.get(f"/api/coleta/tarefas/revisao/?competencia={self.novembro.pk}")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual({r["categoria"] for r in resp.data[0]["responsaveis"]}, {"GG", "SNB1"})
        self.assertTrue(all(r["categoria_nome"] for r in resp.data[0]["responsaveis"]))
