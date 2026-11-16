"""Endpoints de tarefas orientadas por Normativa e atribuições existentes.

Não modifica Cadastro, Normativa ou permissões; mantém APIs legadas para
compatibilidade, mas o novo frontend deve usar somente /tarefas/.
"""
from django.db import transaction
from django.apps import apps
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador
from .tarefas import gerar_tarefas, localizar_tarefa, validar_dados


def garantir_registrador(usuario):
    if not usuario_tem_permissao(usuario, "acesso.registrar_resultado"):
        raise PermissionDenied("Apenas usuários autorizados a registrar podem acessar essas tarefas.")


def competencia_da_requisicao(request):
    chave = request.query_params.get("competencia") if request.method == "GET" else request.data.get("competencia")
    try:
        pk = int(chave)
    except (TypeError, ValueError):
        raise serializers.ValidationError({"competencia": "Informe o ID numérico da competência."}) from None
    return get_object_or_404(CompetenciaColeta.objects.select_related("versao"), pk=pk)


def escopo_e_tarefa(payload, usuario, competencia):
    """Confere autorização e aplicabilidade consultando o mesmo planejador do GET."""
    unidade = payload.get("unidade")
    distrito = payload.get("distrito")
    if (unidade is None) == (distrito is None):
        raise serializers.ValidationError("Informe unidade OU distrito, nunca ambos.")
    try:
        unidade = int(unidade) if unidade is not None else None
        distrito = int(distrito) if distrito is not None else None
        indicador = int(payload.get("indicador"))
    except (ValueError, TypeError):
        raise serializers.ValidationError("Unidade, distrito e indicador devem ser IDs numéricos.") from None
    tarefa = localizar_tarefa(gerar_tarefas(competencia, usuario), unidade_id=unidade,
                              distrito_id=distrito, indicador_id=indicador)
    if tarefa is None:
        # Não revelar se existe unidade/indicador fora das atribuições.
        raise PermissionDenied("Tarefa inexistente ou não atribuída a este Registrador.")
    return unidade, distrito, tarefa


class TarefasColetaView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        garantir_registrador(request.user)
        competencia = competencia_da_requisicao(request)
        return Response(gerar_tarefas(competencia, request.user))


class SalvarTarefaView(APIView):
    """Salva somente folhas preenchíveis de uma tarefa, em transação atômica.

    Exemplo: {"competencia":1,"unidade":2,"indicador":4,
      "itens":[{"codigo":"4.I.1","dados":{"valor":87},"fonte":"PEC"}]}
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        garantir_registrador(request.user)
        competencia = competencia_da_requisicao(request)
        if competencia.estado != CompetenciaColeta.Estado.ABERTA:
            raise serializers.ValidationError("Período de avaliação encerrado.")
        unidade, distrito, tarefa = escopo_e_tarefa(request.data, request.user, competencia)
        itens = request.data.get("itens")
        if not isinstance(itens, list) or not itens:
            raise serializers.ValidationError({"itens": "Envie pelo menos um subindicador preenchido."})
        aplicaveis = {x["codigo"]: x for x in tarefa["itens"] if x["tipo"] == "PREENCHIMENTO"}
        codigos = set()
        # Validar TODO o lote antes de qualquer gravação.
        for item in itens:
            if not isinstance(item, dict) or not isinstance(item.get("codigo"), str):
                raise serializers.ValidationError({"itens": "Cada item exige um código de subindicador."})
            codigo = item["codigo"]
            if codigo in codigos:
                raise serializers.ValidationError({"itens": f"Subindicador repetido: {codigo}."})
            codigos.add(codigo)
            definicao = aplicaveis.get(codigo)
            if definicao is None:
                raise serializers.ValidationError({"itens": f"O subindicador {codigo} não está habilitado para essa tarefa."})
            try:
                validar_dados(definicao["campos"], item.get("dados"))
            except ValueError as erro:
                raise serializers.ValidationError({"itens": f"{codigo}: {erro}"}) from erro
            fonte = item.get("fonte")
            if not isinstance(fonte, str) or not fonte.strip() or len(fonte) > 255:
                raise serializers.ValidationError({"itens": f"{codigo}: informe a fonte (até 255 caracteres)."})
            if not isinstance(item.get("observacoes", ""), str):
                raise serializers.ValidationError({"itens": f"{codigo}: observações devem ser texto."})
        gravados = []
        try:
            with transaction.atomic():
                for item in itens:
                    definicao = aplicaveis[item["codigo"]]
                    consulta = RegistroIndicador.objects.select_for_update(of=("self",)).filter(
                        competencia=competencia, indicador_id=definicao["indicador"],
                        categoria_id=tarefa["categoria"], unidade_id=unidade, distrito_id=distrito,
                    )
                    registro = consulta.first()
                    if registro is None:
                        registro = RegistroIndicador(
                            competencia=competencia, indicador_id=definicao["indicador"],
                            categoria_id=tarefa["categoria"], unidade_id=unidade, distrito_id=distrito,
                            registrado_por=request.user,
                        )
                    else:
                        if registro.registrado_por_id != request.user.pk and not request.user.is_superuser:
                            raise PermissionDenied("O lançamento pertence a outro Registrador.")
                        if registro.situacao not in (
                            RegistroIndicador.Situacao.RASCUNHO, RegistroIndicador.Situacao.DEVOLVIDO
                        ):
                            raise serializers.ValidationError({"itens": f"{item['codigo']} já foi enviado ou homologado."})
                    registro.dados = item["dados"]
                    registro.fonte = item["fonte"].strip()
                    registro.observacoes = item.get("observacoes", "").strip()
                    registro.situacao = RegistroIndicador.Situacao.RASCUNHO
                    registro.motivo_devolucao = ""
                    registro.homologado_por = None
                    registro.decidido_em = None
                    registro.save()  # full_clean() valida vínculo com categoria, versão e competência.
                    gravados.append({"codigo": item["codigo"], "registro_id": registro.pk})
        except DjangoValidationError as erro:
            raise serializers.ValidationError(getattr(erro, "message_dict", erro.messages)) from erro
        return Response({"salvos": gravados}, status=status.HTTP_200_OK)


class EnviarTarefaView(APIView):
    """Envia um grupo somente se todas as folhas disponíveis foram preenchidas.

    Folhas indisponíveis não são consideradas nota zero nem obrigatoriedade.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        garantir_registrador(request.user)
        competencia = competencia_da_requisicao(request)
        if competencia.estado != CompetenciaColeta.Estado.ABERTA:
            raise serializers.ValidationError("Período de avaliação encerrado.")
        unidade, distrito, tarefa = escopo_e_tarefa(request.data, request.user, competencia)
        habilitados = [item for item in tarefa["itens"] if item["tipo"] == "PREENCHIMENTO"]
        if not habilitados:
            raise serializers.ValidationError("Tarefa indisponível: nenhuma regra habilitada.")
        faltantes = [item["codigo"] for item in habilitados if item["registro_id"] is None]
        if faltantes:
            raise serializers.ValidationError({"pendentes": faltantes})
        enviados = []
        with transaction.atomic():
            registros = list(RegistroIndicador.objects.select_for_update(of=("self",)).filter(
                competencia=competencia, categoria_id=tarefa["categoria"],
                unidade_id=unidade, distrito_id=distrito,
                indicador_id__in=[item["indicador"] for item in habilitados],
            ))
            if len(registros) != len(habilitados):
                raise serializers.ValidationError("Alguns lançamentos ainda estão pendentes.")
            if any(r.registrado_por_id != request.user.pk and not request.user.is_superuser for r in registros):
                raise PermissionDenied("A tarefa contém um registro de outro autor.")
            alteraveis = [r for r in registros if r.situacao in (
                RegistroIndicador.Situacao.RASCUNHO, RegistroIndicador.Situacao.DEVOLVIDO
            )]
            if not alteraveis:
                raise serializers.ValidationError("Não há rascunhos ou devoluções para envio.")
            for registro in alteraveis:
                registro.situacao = RegistroIndicador.Situacao.ENVIADO
                registro.enviado_em = timezone.now()
                registro.motivo_devolucao = ""
                registro.homologado_por = None
                registro.decidido_em = None
                try:
                    registro.save()
                except DjangoValidationError as erro:
                    raise serializers.ValidationError(getattr(erro, "message_dict", erro.messages)) from erro
                enviados.append(registro.pk)
        return Response({"enviados": len(enviados), "registro_ids": enviados})


class OpcoesColetaView(APIView):
    """Rota LEGADA mantida para não quebrar o frontend atual e os testes antigos.

    Novas telas devem consultar /tarefas/; aqui mantemos o contrato prévio
    de escopos + indicadores filtrados por regras/categoria.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        garantir_registrador(request.user)
        competencia = competencia_da_requisicao(request)
        Unidade = apps.get_model("cadastro", "Unidade")
        Distrito = apps.get_model("cadastro", "Distrito")
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        Regra = apps.get_model("normativa", "RegraIndicador")
        if request.user.is_superuser:
            unidades = Unidade.objects.select_related("tipo__categoria", "distrito").filter(ativa=True)
            distritos = Distrito.objects.filter(ativo=True)
        else:
            autorizacoes = AutorizacaoColeta.objects.filter(usuario=request.user)
            ids_unidades = autorizacoes.exclude(unidade_id=None).values_list("unidade_id", flat=True)
            ids_distritos = autorizacoes.exclude(distrito_id=None).values_list("distrito_id", flat=True)
            unidades = Unidade.objects.select_related("tipo__categoria", "distrito").filter(
                Q(pk__in=ids_unidades) | Q(distrito_id__in=ids_distritos), ativa=True
            ).distinct()
            distritos = Distrito.objects.filter(pk__in=ids_distritos, ativo=True)

        escopos = []
        for unidade in unidades.order_by("nome"):
            escopos.append({
                "tipo": "UNIDADE", "id": unidade.id, "nome": unidade.nome,
                "categoria": unidade.tipo.categoria_id,
                "categoria_codigo": unidade.tipo.categoria.codigo,
            })
        categorias_distrito = list(Categoria.objects.filter(escopo="DISTRITO").order_by("codigo"))
        for distrito in distritos.order_by("codigo"):
            for categoria in categorias_distrito:
                escopos.append({
                    "tipo": "DISTRITO", "id": distrito.id, "nome": distrito.nome,
                    "categoria": categoria.id, "categoria_codigo": categoria.codigo,
                })
        categorias = {e["categoria"] for e in escopos}
        regras = Regra.objects.filter(
            indicador__versao_id=competencia.versao_id, categoria_id__in=categorias
        ).select_related("indicador").order_by("indicador__codigo", "categoria_id")
        indicadores = [{
            "id": regra.indicador_id, "codigo": regra.indicador.codigo,
            "nome": regra.indicador.nome, "categoria": regra.categoria_id,
        } for regra in regras]
        return Response({"escopos": escopos, "indicadores": indicadores})
