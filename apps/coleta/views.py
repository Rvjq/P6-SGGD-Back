"""API de Coleta: registros próprios, envio e revisão com separação de funções."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.acesso.interface import usuario_tem_permissao

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador
from .permissions import pode_lancar
from .serializers import AutorizacaoSerializer, CompetenciaSerializer, RegistroSerializer


def exigir(usuario, permissao):
    if not usuario_tem_permissao(usuario, permissao):
        raise PermissionDenied("Você não tem permissão para esta operação.")


def validar_modelo_salvar(registro):
    try:
        registro.save()
    except DjangoValidationError as erro:
        if hasattr(erro, "message_dict"):
            raise serializers.ValidationError(erro.message_dict) from erro
        raise serializers.ValidationError(erro.messages) from erro


class CompetenciaViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    queryset = CompetenciaColeta.objects.select_related("versao")
    serializer_class = CompetenciaSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in ("POST", "PATCH"):
            exigir(request.user, "acesso.gerenciar_competencia")
        elif not any(usuario_tem_permissao(request.user, p) for p in (
            "acesso.gerenciar_competencia", "acesso.registrar_resultado", "acesso.homologar_resultado"
        )):
            raise PermissionDenied()

    def partial_update(self, request, *args, **kwargs):
        if set(request.data) != {"estado"}:
            raise serializers.ValidationError("Só é permitido alterar o estado da competência.")
        competencia = self.get_object()
        novo_estado = request.data.get("estado")
        if competencia.estado == CompetenciaColeta.Estado.FECHADA:
            raise serializers.ValidationError("Competência fechada não pode ser reaberta nesta etapa.")
        if novo_estado == CompetenciaColeta.Estado.FECHADA and competencia.registros.exclude(
            situacao=RegistroIndicador.Situacao.HOMOLOGADO
        ).exists():
            raise serializers.ValidationError(
                "Existem registros não homologados. Resolva-os antes de fechar a competência."
            )
        return super().partial_update(request, *args, **kwargs)


class AutorizacaoViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    queryset = AutorizacaoColeta.objects.select_related("usuario", "unidade", "distrito")
    serializer_class = AutorizacaoSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ("get", "post", "delete", "head", "options")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        exigir(request.user, "acesso.cadastrar_unidade")


class RegistroViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    queryset = RegistroIndicador.objects.select_related(
        "competencia", "indicador", "categoria", "unidade", "distrito", "registrado_por"
    )
    serializer_class = RegistroSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        usuario = self.request.user
        if usuario.is_superuser:
            qs = self.queryset
        elif usuario_tem_permissao(usuario, "acesso.homologar_resultado"):
            qs = self.queryset.filter(
                Q(situacao__in=(
                    RegistroIndicador.Situacao.ENVIADO,
                    RegistroIndicador.Situacao.HOMOLOGADO,
                    RegistroIndicador.Situacao.DEVOLVIDO,
                )) | Q(registrado_por=usuario)
            )
        elif usuario_tem_permissao(usuario, "acesso.registrar_resultado"):
            qs = self.queryset.filter(registrado_por=usuario)
        else:
            return self.queryset.none()
        competencia = self.request.query_params.get("competencia")
        situacao = self.request.query_params.get("situacao")
        if competencia:
            qs = qs.filter(competencia_id=competencia)
        if situacao:
            qs = qs.filter(situacao=situacao)
        return qs

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.action in ("homologar", "devolver"):
            exigir(request.user, "acesso.homologar_resultado")
        elif self.action in ("create", "partial_update", "update", "enviar"):
            exigir(request.user, "acesso.registrar_resultado")
        elif not (
            usuario_tem_permissao(request.user, "acesso.registrar_resultado")
            or usuario_tem_permissao(request.user, "acesso.homologar_resultado")
        ):
            raise PermissionDenied()

    def perform_create(self, serializer):
        dados = serializer.validated_data
        if not pode_lancar(self.request.user, unidade=dados.get("unidade"), distrito=dados.get("distrito")):
            raise PermissionDenied("Sem autorização de coleta para a unidade/distrito.")
        if dados["competencia"].estado != CompetenciaColeta.Estado.ABERTA:
            raise serializers.ValidationError("Competência fechada.")
        serializer.save(registrado_por=self.request.user)

    def perform_update(self, serializer):
        instancia = serializer.instance
        if instancia.registrado_por_id != self.request.user.pk:
            raise PermissionDenied("Apenas o autor pode corrigir seu registro.")
        if instancia.situacao not in (
            RegistroIndicador.Situacao.RASCUNHO,
            RegistroIndicador.Situacao.DEVOLVIDO,
        ):
            raise serializers.ValidationError("Somente rascunhos ou devolvidos podem ser corrigidos.")
        if instancia.competencia.estado != CompetenciaColeta.Estado.ABERTA:
            raise serializers.ValidationError("Competência fechada.")
        if not pode_lancar(self.request.user, unidade=instancia.unidade, distrito=instancia.distrito):
            raise PermissionDenied("Autorização de coleta revogada.")
        serializer.save(situacao=RegistroIndicador.Situacao.RASCUNHO)

    @action(detail=True, methods=("post",))
    def enviar(self, request, pk=None):
        with transaction.atomic():
            registro = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
            if registro.registrado_por_id != request.user.pk:
                raise PermissionDenied("Apenas o autor pode enviar o registro.")
            if registro.situacao not in (RegistroIndicador.Situacao.RASCUNHO, RegistroIndicador.Situacao.DEVOLVIDO):
                raise serializers.ValidationError("Somente rascunhos ou devolvidos podem ser enviados.")
            if registro.competencia.estado != CompetenciaColeta.Estado.ABERTA:
                raise serializers.ValidationError("Competência fechada.")
            if not pode_lancar(request.user, unidade=registro.unidade, distrito=registro.distrito):
                raise PermissionDenied("Sem autorização vigente de coleta.")
            registro.situacao = RegistroIndicador.Situacao.ENVIADO
            registro.enviado_em = timezone.now()
            registro.motivo_devolucao = ""
            registro.homologado_por = None
            registro.decidido_em = None
            validar_modelo_salvar(registro)
        return Response(self.get_serializer(registro).data)

    @action(detail=True, methods=("post",))
    def homologar(self, request, pk=None):
        with transaction.atomic():
            registro = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
            if registro.situacao != RegistroIndicador.Situacao.ENVIADO:
                raise serializers.ValidationError("Somente registros enviados podem ser homologados.")
            if registro.registrado_por_id == request.user.pk:
                raise PermissionDenied("Não é permitido homologar o próprio registro.")
            registro.situacao = RegistroIndicador.Situacao.HOMOLOGADO
            registro.homologado_por = request.user
            registro.decidido_em = timezone.now()
            validar_modelo_salvar(registro)
        return Response(self.get_serializer(registro).data)

    @action(detail=True, methods=("post",))
    def devolver(self, request, pk=None):
        motivo = request.data.get("motivo", "")
        if not isinstance(motivo, str) or not motivo.strip():
            raise serializers.ValidationError({"motivo": "Informe uma justificativa para devolução."})
        with transaction.atomic():
            registro = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
            if registro.situacao != RegistroIndicador.Situacao.ENVIADO:
                raise serializers.ValidationError("Somente registros enviados podem ser devolvidos.")
            if registro.registrado_por_id == request.user.pk:
                raise PermissionDenied("Não é permitido revisar o próprio registro.")
            registro.situacao = RegistroIndicador.Situacao.DEVOLVIDO
            registro.motivo_devolucao = motivo.strip()
            registro.homologado_por = request.user
            registro.decidido_em = timezone.now()
            validar_modelo_salvar(registro)
        return Response(self.get_serializer(registro).data)


