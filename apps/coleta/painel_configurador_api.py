"""Contadores administrativos e progresso por Registrador para o Configurador.

Os números refletem a base real; a produtividade depende das atribuições vigentes.
Atribuições ainda não estão associadas a uma competência (limitação conhecida).
"""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao
from .models import AutorizacaoColeta, CompetenciaColeta
from .resumo_api import consolidar_tarefas
from .tarefas import gerar_tarefas


class PainelConfiguradorView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        if not usuario_tem_permissao(request.user, "acesso.gerenciar_competencia"):
            raise PermissionDenied("Painel reservado ao Configurador.")
        Usuario = get_user_model()
        Unidade = apps.get_model("cadastro", "Unidade")
        Distrito = apps.get_model("cadastro", "Distrito")
        Pessoa = apps.get_model("cadastro", "PessoaAvaliada")
        Versao = apps.get_model("normativa", "VersaoNormativa")
        competencias = CompetenciaColeta.objects.select_related("versao").order_by("-mes")
        raw = request.query_params.get("competencia")
        if raw:
            try:
                competencia = get_object_or_404(competencias, pk=int(raw))
            except (TypeError, ValueError):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"competencia": "Informe um ID numérico válido."}) from None
        else:
            competencia = competencias.filter(estado="ABERTA").first() or competencias.first()
        registradores = (Usuario.objects.filter(groups__name="Registrador", is_active=True)
                         .distinct().order_by("first_name", "email", "pk"))
        progresso = []
        planos = []
        for user in registradores:
            plano = gerar_tarefas(competencia, user) if competencia else {"escopos": []}
            totais, escopos = consolidar_tarefas([plano])
            if competencia:
                planos.append(plano)
            progresso.append({"id": user.pk, "nome": user.get_full_name() or user.email,
                             "email": user.email, "escopos": escopos, "tarefas": totais,
                             "percentual_entregue": round(100 * (totais["ENVIADA"] + totais["HOMOLOGADA"]) / totais["TOTAL"]) if totais["TOTAL"] else 0})
        totais_gerais, escopos_gerais = consolidar_tarefas(planos)
        versao = competencia.versao if competencia else Versao.objects.order_by("codigo").first()
        return Response({
            "competencia": competencia.pk if competencia else None,
            "mes": competencia.mes.isoformat() if competencia else None,
            "normativa": {"id": versao.pk, "codigo": versao.codigo, "titulo": versao.titulo} if versao else None,
            "contagens": {"usuarios": Usuario.objects.count(), "unidades": Unidade.objects.count(),
                          "distritos": Distrito.objects.count(), "avaliados": Pessoa.objects.count(),
                          "atribuicoes": AutorizacaoColeta.objects.count(),
                          "registradores": registradores.count(), "escopos": escopos_gerais},
            "tarefas": totais_gerais,
            "registradores": progresso,
            "observacao": "Progresso derivado dos lançamentos reais; atribuições ainda não são limitadas por período.",
        })
