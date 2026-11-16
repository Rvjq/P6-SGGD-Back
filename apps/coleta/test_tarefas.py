"""Testes das tarefas guiadas usando o catálogo CAM 1.2 real importado."""
from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador


class TarefasCam12Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("importar_cam12", verbosity=0)
        call_command("configurar_regras_cam12", verbosity=0)
        Usuario = get_user_model()
        cls.reg = Usuario.objects.create_user(username="reg-tarefas", email="tarefas@exemplo.com", password="teste")
        cls.outro = Usuario.objects.create_user(username="out-tarefas", email="outtarefas@exemplo.com", password="teste")
        cls.cons = Usuario.objects.create_user(username="cons-tarefas", email="constarefas@exemplo.com", password="teste")
        cls.reg.groups.add(Group.objects.get(name="Registrador"))
        cls.outro.groups.add(Group.objects.get(name="Registrador"))
        cls.cons.groups.add(Group.objects.get(name="Consultador"))
        Distrito = apps.get_model("cadastro", "Distrito")
        TipoUnidade = apps.get_model("cadastro", "TipoUnidade")
        Unidade = apps.get_model("cadastro", "Unidade")
        Versao = apps.get_model("normativa", "VersaoNormativa")
        Indicador = apps.get_model("normativa", "Indicador")
        cls.versao = Versao.objects.get(codigo="CAM 1.2")
        cls.i4 = Indicador.objects.get(versao=cls.versao, codigo="4")
        cls.i5 = Indicador.objects.get(versao=cls.versao, codigo="5")
        cls.i1 = Indicador.objects.get(versao=cls.versao, codigo="1")
        cls.d1 = Distrito.objects.get(codigo="I")
        cls.d2 = Distrito.objects.get(codigo="II")
        cls.usf = Unidade.objects.create(codigo="U-TAR-USF", nome="USF de Teste", distrito=cls.d1,
                                         tipo=TipoUnidade.objects.get(codigo="USF"))
        cls.caps = Unidade.objects.create(codigo="U-TAR-CAPS", nome="CAPS de Teste", distrito=cls.d1,
                                          tipo=TipoUnidade.objects.get(codigo="CAPS"))
        cls.ubt = Unidade.objects.create(codigo="U-TAR-UBT", nome="UBT Fora", distrito=cls.d2,
                                         tipo=TipoUnidade.objects.get(codigo="UBT"))
        cls.competencia = CompetenciaColeta.objects.create(mes=date(2026, 11, 1), versao=cls.versao)
        AutorizacaoColeta.objects.create(usuario=cls.reg, distrito=cls.d1)
        cls.pessoa_gg = apps.get_model("cadastro", "PessoaAvaliada").objects.create(
            codigo="TAR-GG", nome="Gerente distrital teste"
        )
        apps.get_model("cadastro", "Responsabilidade").objects.create(
            pessoa=cls.pessoa_gg, distrito=cls.d1,
            categoria=apps.get_model("cadastro", "CategoriaAvaliacao").objects.get(codigo="GG"),
            data_inicio=date(2026, 1, 1),
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(user=self.reg)

    def plano(self):
        resposta = self.api.get(f"/api/coleta/tarefas/?competencia={self.competencia.pk}")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data

    def tarefa(self, plano, unidade, codigo):
        escopo = next(e for e in plano["escopos"] if e["tipo"] == "UNIDADE" and e["id"] == unidade.pk)
        return next(t for t in escopo["tarefas"] if t["codigo"] == codigo)

    def item_4_usf(self, codigo="4.I.1", valor=87):
        return {"codigo": codigo, "dados": {"valor": valor}, "fonte": "PEC / SISAB"}

    def salvar(self, itens, *, unidade=None, distrito=None, indicador=None):
        return self.api.post("/api/coleta/tarefas/salvar/", {
            "competencia": self.competencia.pk,
            "unidade": (unidade or self.usf).pk if distrito is None else None,
            "distrito": distrito.pk if distrito is not None else None,
            "indicador": (indicador or self.i4).pk,
            "itens": itens,
        }, format="json")

    def enviar(self, *, unidade=None, distrito=None, indicador=None):
        return self.api.post("/api/coleta/tarefas/enviar/", {
            "competencia": self.competencia.pk,
            "unidade": (unidade or self.usf).pk if distrito is None else None,
            "distrito": distrito.pk if distrito is not None else None,
            "indicador": (indicador or self.i4).pk,
        }, format="json")

    def test_tarefas_automaticas_usf_caps_e_distrito(self):
        plano = self.plano()
        escopos = plano["escopos"]
        self.assertEqual(len([e for e in escopos if e["tipo"] == "UNIDADE"]), 2)
        self.assertEqual(len([e for e in escopos if e["tipo"] == "DISTRITO"]), 1)
        self.assertFalse(any(e["id"] == self.ubt.pk and e["tipo"] == "UNIDADE" for e in escopos))
        usf_i4 = self.tarefa(plano, self.usf, "4")
        self.assertEqual(len(usf_i4["itens"]), 11)
        self.assertEqual(len([i for i in usf_i4["itens"] if i["tipo"] == "PREENCHIMENTO"]), 10)
        self.assertEqual(usf_i4["campos_total"], 10)
        self.assertEqual(usf_i4["situacao"], "NAO_INICIADA")
        self.assertEqual(len(self.tarefa(plano, self.caps, "4")["itens"]), 6)
        distrital = next(e for e in escopos if e["tipo"] == "DISTRITO")
        self.assertEqual([t["codigo"] for t in distrital["tarefas"]], ["5"])
        self.assertEqual(RegistroIndicador.objects.count(), 0, "Listar tarefas não deve criar registros vazios.")

    def test_terceiro_sem_atribuicao_nao_ve_escopos(self):
        self.api.force_authenticate(user=self.outro)
        response = self.api.get(f"/api/coleta/tarefas/?competencia={self.competencia.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["escopos"], [])
        self.assertEqual(self.salvar([self.item_4_usf()]).status_code, 403)

    def test_consultador_nao_e_registrador(self):
        self.api.force_authenticate(user=self.cons)
        self.assertEqual(self.api.get(f"/api/coleta/tarefas/?competencia={self.competencia.pk}").status_code, 403)

    def test_rascunho_parcial_e_idempotente(self):
        self.assertEqual(self.salvar([self.item_4_usf()]).status_code, 200)
        resposta = self.salvar([self.item_4_usf(valor=92)])
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(RegistroIndicador.objects.count(), 1)
        plano = self.plano()
        tarefa = self.tarefa(plano, self.usf, "4")
        self.assertEqual(tarefa["situacao"], "EM_ANDAMENTO")
        self.assertEqual(tarefa["campos_preenchidos"], 1)
        item = next(i for i in tarefa["itens"] if i["codigo"] == "4.I.1")
        self.assertEqual(item["dados"], {"valor": 92})

    def test_regras_pendentes_e_escopo_invalido_bloqueados(self):
        self.assertEqual(self.salvar([self.item_4_usf(codigo="4.I.10")]).status_code, 400)
        self.assertEqual(self.salvar([self.item_4_usf(codigo="4.II.1")]).status_code, 400)
        self.assertEqual(self.salvar([self.item_4_usf()], unidade=self.ubt).status_code, 403)
        self.assertEqual(RegistroIndicador.objects.count(), 0)

    def test_formato_de_dados_validado_sem_aceitar_lixos(self):
        self.assertEqual(self.salvar([self.item_4_usf(valor="abc")]).status_code, 400)
        self.assertEqual(self.salvar([{"codigo": "4.I.1", "dados": {"x": 8}, "fonte": "PEC"}]).status_code, 400)
        self.assertEqual(self.salvar([{"codigo": "4.I.1", "dados": {"valor": 80}, "fonte": ""}]).status_code, 400)
        response = self.salvar([{"codigo": "1", "dados": {"numerador": 12, "denominador": 0}, "fonte": "Hórus"}], indicador=self.i1)
        self.assertEqual(response.status_code, 400)

    def test_envio_agrupado_ignora_item_indisponivel(self):
        self.assertEqual(self.enviar().status_code, 400, "Não pode enviar tarefa vazia.")
        codigos = [i["codigo"] for i in self.tarefa(self.plano(), self.usf, "4")["itens"] if i["tipo"] == "PREENCHIMENTO"]
        resposta = self.salvar([self.item_4_usf(codigo=c) for c in codigos])
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(len(resposta.data["salvos"]), 10)
        resposta = self.enviar()
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["enviados"], 10)
        self.assertEqual(self.tarefa(self.plano(), self.usf, "4")["situacao"], "ENVIADA")
        self.assertEqual(self.salvar([self.item_4_usf()]).status_code, 400)

    def test_distrito_tem_tarefa_especifica_sem_registro_de_consolidacao(self):
        response = self.salvar([{"codigo": "5.I", "dados": {"valor": 82}, "fonte": "SIM"}], distrito=self.d1, indicador=self.i5)
        self.assertEqual(response.status_code, 200, response.data)
        obj = RegistroIndicador.objects.get(indicador__codigo="5.I")
        self.assertEqual(obj.distrito, self.d1)
        self.assertIsNone(obj.unidade_id)
        self.assertEqual(obj.categoria.codigo, "GG")
        self.assertEqual(RegistroIndicador.objects.count(), 1)

    def test_terceiro_nao_le_valores_do_autor(self):
        self.assertEqual(self.salvar([self.item_4_usf()]).status_code, 200)
        AutorizacaoColeta.objects.create(usuario=self.outro, unidade=self.usf)
        self.api.force_authenticate(user=self.outro)
        tarefa = self.tarefa(self.plano(), self.usf, "4")
        item = next(i for i in tarefa["itens"] if i["codigo"] == "4.I.1")
        self.assertEqual(item["situacao"], "ATRIBUIDO_A_OUTRO")
        self.assertIsNone(item["dados"])
        self.assertEqual(item["fonte"], "")
        self.assertEqual(self.salvar([self.item_4_usf()]).status_code, 403)

    def test_sem_sobrescrever_em_competencia_fechada(self):
        self.competencia.estado = CompetenciaColeta.Estado.FECHADA
        self.competencia.save()
        self.assertEqual(self.salvar([self.item_4_usf()]).status_code, 400)
        self.assertEqual(self.enviar().status_code, 400)

    def test_revisao_agrupada_homologa_todos_os_subindicadores(self):
        Usuario = get_user_model()
        hom = Usuario.objects.create_user(username="hom-tarefas", email="homtarefas@exemplo.com", password="teste")
        hom.groups.add(Group.objects.get(name="Homologador"))
        codigos = [i["codigo"] for i in self.tarefa(self.plano(), self.usf, "4")["itens"] if i["tipo"] == "PREENCHIMENTO"]
        self.assertEqual(self.salvar([self.item_4_usf(codigo=c) for c in codigos]).status_code, 200)
        self.assertEqual(self.enviar().status_code, 200)
        self.api.force_authenticate(user=hom)
        resposta = self.api.get(f"/api/coleta/tarefas/revisao/?competencia={self.competencia.pk}")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        grupo = next(g for g in resposta.data if g["indicador_codigo"] == "4")
        self.assertEqual(len(grupo["itens"]), 10)
        ids = [i["id"] for i in grupo["itens"]]
        resposta = self.api.post("/api/coleta/tarefas/decidir/", {
            "ids": ids, "decisao": "HOMOLOGAR"
        }, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(RegistroIndicador.objects.filter(
            id__in=ids, situacao="HOMOLOGADO").count(), len(ids))
        self.assertFalse(any(g["indicador_codigo"] == "4" for g in self.api.get(
            f"/api/coleta/tarefas/revisao/?competencia={self.competencia.pk}").data))

    def test_revisao_nao_aceita_usuario_sem_papel_nem_proprio_autor(self):
        codigos = [i["codigo"] for i in self.tarefa(self.plano(), self.usf, "4")["itens"] if i["tipo"] == "PREENCHIMENTO"]
        self.assertEqual(self.salvar([self.item_4_usf(codigo=c) for c in codigos]).status_code, 200)
        self.assertEqual(self.enviar().status_code, 200)
        ids = list(RegistroIndicador.objects.filter(
            competencia=self.competencia, unidade=self.usf).values_list("id", flat=True))
        self.assertEqual(self.api.get(
            f"/api/coleta/tarefas/revisao/?competencia={self.competencia.pk}").status_code, 403)
        self.assertEqual(self.api.post("/api/coleta/tarefas/decidir/", {
            "ids": ids, "decisao": "HOMOLOGAR"
        }, format="json").status_code, 403)
        self.reg.groups.add(Group.objects.get(name="Homologador"))
        self.assertEqual(self.api.post("/api/coleta/tarefas/decidir/", {
            "ids": ids, "decisao": "HOMOLOGAR"
        }, format="json").status_code, 403)

    def test_revisao_devolucao_exige_justificativa(self):
        Usuario = get_user_model()
        hom = Usuario.objects.create_user(username="hom-outro", email="homoutro@exemplo.com", password="teste")
        hom.groups.add(Group.objects.get(name="Homologador"))
        codigos = [i["codigo"] for i in self.tarefa(self.plano(), self.usf, "4")["itens"] if i["tipo"] == "PREENCHIMENTO"]
        self.assertEqual(self.salvar([self.item_4_usf(codigo=c) for c in codigos]).status_code, 200)
        self.assertEqual(self.enviar().status_code, 200)
        ids = list(RegistroIndicador.objects.filter(competencia=self.competencia, unidade=self.usf)
                   .values_list("id", flat=True))
        self.api.force_authenticate(user=hom)
        self.assertEqual(self.api.post("/api/coleta/tarefas/decidir/", {
            "ids": ids, "decisao": "DEVOLVER"
        }, format="json").status_code, 400)
        resposta = self.api.post("/api/coleta/tarefas/decidir/", {
            "ids": ids, "decisao": "DEVOLVER", "motivo": "Conferir relatório"
        }, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(RegistroIndicador.objects.filter(
            id__in=ids, situacao="DEVOLVIDO", motivo_devolucao="Conferir relatório").count(), len(ids))

    def test_configuracao_disponivel_somente_configurador(self):
        self.assertEqual(self.api.get('/api/coleta/configuracao/').status_code, 403)
        Usuario = get_user_model()
        conf = Usuario.objects.create_user(username="cfg-tarefas", email="cfgtarefas@exemplo.com", password="teste")
        conf.groups.add(Group.objects.get(name="Configurador"))
        self.api.force_authenticate(user=conf)
        resposta = self.api.get('/api/coleta/configuracao/')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertTrue(any(u["id"] == self.usf.pk for u in resposta.data["unidades"]))
        self.assertTrue(any(v["codigo"] == "CAM 1.2" for v in resposta.data["versoes"]))

    def test_revisao_nao_aceita_homologacao_parcial(self):
        Usuario = get_user_model()
        hom = Usuario.objects.create_user(username="hom-parcial", email="homparcial@exemplo.com", password="teste")
        hom.groups.add(Group.objects.get(name="Homologador"))
        codigos = [i["codigo"] for i in self.tarefa(self.plano(), self.usf, "4")["itens"] if i["tipo"] == "PREENCHIMENTO"]
        self.assertEqual(self.salvar([self.item_4_usf(codigo=c) for c in codigos]).status_code, 200)
        self.assertEqual(self.enviar().status_code, 200)
        self.api.force_authenticate(user=hom)
        id_parcial = RegistroIndicador.objects.filter(competencia=self.competencia, unidade=self.usf).first().pk
        resposta = self.api.post("/api/coleta/tarefas/decidir/", {
            "ids": [id_parcial], "decisao": "HOMOLOGAR"
        }, format="json")
        self.assertEqual(resposta.status_code, 400)
