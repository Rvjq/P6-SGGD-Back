"""Resumo operacional real da Coleta, com indicadores adequados ao papel.

Sem novas tabelas ou cálculos de nota. Cada tarefa é identificada por
(escopo, localidade, indicador principal); duplicatas de atribuição não
entram duas vezes. O Consultador não recebe dados operacionais privados.
"""
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao
from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador
from .revisao_api import chave_registro
from .tarefas import gerar_tarefas

ESTADOS = ("NAO_INICIADA", "EM_ANDAMENTO", "ENVIADA", "HOMOLOGADA", "DEVOLVIDA", "INDISPONIVEL")
PRIORIDADE = {"INDISPONIVEL": 0, "NAO_INICIADA": 1, "EM_ANDAMENTO": 2,
              "DEVOLVIDA": 3, "ENVIADA": 4, "HOMOLOGADA": 5}


def consolidar_tarefas(planos):
    """Uma tarefa pode aparecer em mais de uma atribuição: contar uma vez."""
    por_chave = {}
    escopos = set()
    for plano in planos:
        for escopo in plano["escopos"]:
            escopos.add((escopo["tipo"], escopo["id"]))
            for tarefa in escopo["tarefas"]:
                chave = (escopo["tipo"], escopo["id"], tarefa["indicador"])
                situacao = tarefa["situacao"]
                if PRIORIDADE.get(situacao, -1) > PRIORIDADE.get(por_chave.get(chave), -1):
                    por_chave[chave] = situacao
    totais = {s: 0 for s in ESTADOS}
    for situacao in por_chave.values():
        if situacao in totais:
            totais[situacao] += 1
    totais["TOTAL"] = sum(v for s, v in totais.items() if s != "INDISPONIVEL")
    return totais, len(escopos)


def contar_revisao(competencia):
    """Uma revisão é o grupo de subindicadores do mesmo indicador principal."""
    grupos = defaultdict(list)
    registros = (RegistroIndicador.objects.filter(competencia=competencia)
                 .select_related("indicador__pai", "categoria"))
    for registro in registros:
        grupos[chave_registro(registro)].append(registro.situacao)
    totais = {s: 0 for s in ESTADOS}
    for situacoes in grupos.values():
        if "ENVIADO" in situacoes:
            totais["ENVIADA"] += 1
        elif "DEVOLVIDO" in situacoes:
            totais["DEVOLVIDA"] += 1
        elif all(s == "HOMOLOGADO" for s in situacoes):
            totais["HOMOLOGADA"] += 1
        else:
            totais["EM_ANDAMENTO"] += 1
    totais["TOTAL"] = len(grupos)
    return totais


class ResumoColetaView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        try:
            pk = int(request.query_params.get("competencia"))
        except (TypeError, ValueError):
            raise serializers.ValidationError({"competencia": "Informe o ID do período."}) from None
        competencia = get_object_or_404(CompetenciaColeta.objects.select_related("versao"), pk=pk)
        user = request.user
        resultado = {"competencia": competencia.pk, "mes": competencia.mes.isoformat(),
                     "estado": competencia.estado, "perfil": "CONSULTADOR", "escopos": 0,
                     "atribuicoes": 0, "operadores": 0, "tarefas": None,
                     "aviso": "Os resultados da avaliação estarão disponíveis após a implementação da Apuração."}

        if usuario_tem_permissao(user, "acesso.gerenciar_competencia"):
            # Apenas perfis operacionais autorizados participam do progresso global.
            usuarios = (get_user_model().objects.filter(
                is_active=True, groups__name="Registrador", autorizacoes_coleta__isnull=False)
                .distinct().order_by("pk"))
            planos = [gerar_tarefas(competencia, registrador) for registrador in usuarios]
            totais, escopos = consolidar_tarefas(planos)
            resultado.update(perfil="CONFIGURADOR", escopos=escopos, tarefas=totais,
                             atribuicoes=AutorizacaoColeta.objects.filter(usuario__is_active=True).count(),
                             operadores=usuarios.count(), aviso="Resumo das tarefas atribuídas, sem cálculo de notas.")
        elif usuario_tem_permissao(user, "acesso.registrar_resultado"):
            totais, escopos = consolidar_tarefas([gerar_tarefas(competencia, user)])
            resultado.update(perfil="REGISTRADOR", escopos=escopos, tarefas=totais,
                             aviso="Contabiliza somente as tarefas visíveis para você.")
        elif usuario_tem_permissao(user, "acesso.homologar_resultado"):
            resultado.update(perfil="HOMOLOGADOR", tarefas=contar_revisao(competencia),
                             aviso="Contabiliza tarefas com lançamentos existentes, não todo o catálogo.")
        return Response(resultado)
