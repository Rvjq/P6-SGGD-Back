"""Homologação por indicador principal (subindicadores decididos em conjunto).

Esta etapa valida os DADOS coletados: não calcula notas, não libera valores
financeiros nem substitui a análise final da CAM. O papel Homologador tem escopo
global na versão acadêmica atual; futuras atribuições por território são outra
etapa, não uma autorização implícita.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao
from .models import CompetenciaColeta, RegistroIndicador


ESTADOS_REVISAO = ("ENVIADO", "HOMOLOGADO", "DEVOLVIDO")


def exigir_homologador(usuario):
    if not usuario_tem_permissao(usuario, "acesso.homologar_resultado"):
        raise PermissionDenied("Apenas Homologadores podem revisar lançamentos.")


def raiz(indicador):
    while indicador.pai_id is not None:
        indicador = indicador.pai
    return indicador


def chave_registro(registro):
    principal = raiz(registro.indicador)
    return (registro.competencia_id, registro.unidade_id, registro.distrito_id,
            registro.categoria_id, principal.pk)


class RevisaoTarefasView(APIView):
    """Consulta ENVIADO por padrão; TODOS inclui homologados e devolvidos.

    Os itens sempre são agrupados por ESTADO para não misturar lançamentos
    já decididos com aqueles ainda aguardando homologação.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        exigir_homologador(request.user)
        try:
            competencia_id = int(request.query_params.get("competencia"))
            if competencia_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise serializers.ValidationError({"competencia": "Selecione um período válido."}) from None

        estado = request.query_params.get("situacao", "ENVIADO").upper()
        if estado not in (*ESTADOS_REVISAO, "TODOS"):
            raise serializers.ValidationError({"situacao": "Use ENVIADO, HOMOLOGADO, DEVOLVIDO ou TODOS."})

        competencia = get_object_or_404(CompetenciaColeta, pk=competencia_id)
        consulta = RegistroIndicador.objects.filter(competencia=competencia)
        if estado == "TODOS":
            consulta = consulta.filter(situacao__in=ESTADOS_REVISAO)
        else:
            consulta = consulta.filter(situacao=estado)
        registros = consulta.select_related(
            "indicador__pai__pai", "categoria", "unidade__distrito", "distrito",
            "registrado_por", "homologado_por",
        )

        # Uma tarefa por indicador / local / categoria / situação.
        grupos = defaultdict(list)
        for registro in registros:
            grupos[(*chave_registro(registro), registro.situacao)].append(registro)

        inicio = competencia.mes
        fim = date(inicio.year, inicio.month, monthrange(inicio.year, inicio.month)[1])
        ids_unidades = {chave[1] for chave in grupos if chave[1] is not None}
        ids_distritos = {chave[2] for chave in grupos if chave[2] is not None}
        por_unidade, por_distrito = defaultdict(list), defaultdict(list)
        if ids_unidades or ids_distritos:
            Responsabilidade = apps.get_model("cadastro", "Responsabilidade")
            vinculos = Responsabilidade.objects.filter(
                pessoa__ativa=True, data_inicio__lte=fim,
            ).filter(
                Q(data_fim__isnull=True) | Q(data_fim__gte=inicio)
            ).filter(
                Q(unidade_id__in=ids_unidades) | Q(distrito_id__in=ids_distritos)
            ).select_related("pessoa", "categoria")
            for vinculo in vinculos:
                destino = por_unidade if vinculo.unidade_id else por_distrito
                local_id = vinculo.unidade_id or vinculo.distrito_id
                destino[local_id].append({
                    "id": vinculo.pessoa_id,
                    "nome": vinculo.pessoa.nome,
                    "categoria": vinculo.categoria.codigo,
                    "categoria_nome": vinculo.categoria.nome,
                })

        resposta = []
        for chave, itens in grupos.items():
            primeiro = itens[0]
            principal = raiz(primeiro.indicador)
            distrito = primeiro.unidade.distrito if primeiro.unidade_id else primeiro.distrito
            autor = primeiro.registrado_por
            revisor = next((r.homologado_por for r in itens if r.homologado_por_id), None)
            resposta.append({
                "competencia": competencia_id,
                "unidade": primeiro.unidade_id,
                "distrito": primeiro.distrito_id,
                "distrito_grupo": distrito.pk,
                "distrito_nome": distrito.nome,
                "escopo_nome": primeiro.unidade.nome if primeiro.unidade_id else distrito.nome,
                "categoria": primeiro.categoria.codigo,
                "indicador": principal.pk,
                "indicador_codigo": principal.codigo,
                "indicador_nome": principal.nome,
                "situacao": chave[-1],
                "registrador": (autor.get_full_name().strip() or autor.email),
                "registrador_email": autor.email,
                "revisado_por": (revisor.get_full_name().strip() or revisor.email) if revisor else None,
                "enviado_em": max((r.enviado_em for r in itens if r.enviado_em), default=None),
                "decidido_em": max((r.decidido_em for r in itens if r.decidido_em), default=None),
                "motivo_devolucao": next((r.motivo_devolucao for r in itens if r.motivo_devolucao), ""),
                "responsaveis": (
                    por_unidade.get(primeiro.unidade_id, []) if primeiro.unidade_id
                    else por_distrito.get(primeiro.distrito_id, [])
                ),
                "itens": [{
                    "id": r.pk, "codigo": r.indicador.codigo, "nome": r.indicador.nome,
                    "dados": r.dados, "fonte": r.fonte, "observacoes": r.observacoes,
                    "situacao": r.situacao, "registrado_por": r.registrado_por_id,
                } for r in sorted(itens, key=lambda x: x.indicador.codigo)],
            })
        return Response(sorted(resposta, key=lambda g: (
            g["distrito_nome"], g["escopo_nome"], g["indicador_codigo"], g["situacao"]
        )))


class DecidirTarefaView(APIView):
    """Homologa/devolve *todos* os itens enviados de uma única tarefa.

    Compatível com o contrato de IDs já utilizado pelo frontend. A transação
    inteira é revertida se faltar um item, houver status inválido ou houver
    tentativa de revisar o próprio lançamento.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        exigir_homologador(request.user)
        decisao = request.data.get("decisao")
        if decisao not in ("HOMOLOGAR", "DEVOLVER"):
            raise serializers.ValidationError({"decisao": "Use HOMOLOGAR ou DEVOLVER."})
        motivo = request.data.get("motivo", "")
        if not isinstance(motivo, str):
            raise serializers.ValidationError({"motivo": "A justificativa deve ser texto."})
        motivo = motivo.strip()
        if decisao == "DEVOLVER" and not motivo:
            raise serializers.ValidationError({"motivo": "A devolução exige uma justificativa."})
        if len(motivo) > 2000:
            raise serializers.ValidationError({"motivo": "Use até 2.000 caracteres."})

        ids = request.data.get("ids")
        if (not isinstance(ids, list) or not (1 <= len(ids) <= 200)
                or any(type(pk) is not int or pk <= 0 for pk in ids)
                or len(ids) != len(set(ids))):
            raise serializers.ValidationError({"ids": "Informe de 1 a 200 IDs únicos e válidos."})

        with transaction.atomic():
            # Lock somente em RegistroIndicador, sem bloquear LEFT JOINs opcionais.
            registros = list(RegistroIndicador.objects.filter(pk__in=ids)
                             .order_by("pk").select_for_update(of=("self",)))
            if len(registros) != len(ids) or any(r.situacao != "ENVIADO" for r in registros):
                raise serializers.ValidationError("Todos os registros devem existir e estar enviados.")
            if len({chave_registro(r) for r in registros}) != 1:
                raise serializers.ValidationError("Selecione apenas um indicador e local por decisão.")
            if len({r.registrado_por_id for r in registros}) != 1:
                raise serializers.ValidationError("Há diferentes autores; é necessária revisão da coleta.")
            if any(r.registrado_por_id == request.user.pk for r in registros):
                raise PermissionDenied("Você não pode revisar seus próprios lançamentos.")

            # Impede aceitar/devolver apenas parte dos itens enviados da tarefa.
            primeiro = registros[0]
            enviados_no_escopo = RegistroIndicador.objects.filter(
                competencia_id=primeiro.competencia_id,
                categoria_id=primeiro.categoria_id,
                unidade_id=primeiro.unidade_id,
                distrito_id=primeiro.distrito_id,
                situacao="ENVIADO",
            ).select_related("indicador__pai__pai")
            ids_tarefa = {r.pk for r in enviados_no_escopo
                          if chave_registro(r) == chave_registro(primeiro)}
            if set(ids) != ids_tarefa:
                raise serializers.ValidationError("Envie todos os subindicadores pendentes desse indicador.")

            situacao = "HOMOLOGADO" if decisao == "HOMOLOGAR" else "DEVOLVIDO"
            agora = timezone.now()
            for registro in registros:
                registro.situacao = situacao
                registro.homologado_por = request.user
                registro.decidido_em = agora
                registro.motivo_devolucao = motivo if decisao == "DEVOLVER" else ""
                try:
                    registro.save()
                except DjangoValidationError as erro:
                    raise serializers.ValidationError(
                        getattr(erro, "message_dict", erro.messages)
                    ) from erro
        return Response({"alterados": len(registros), "situacao": situacao})
