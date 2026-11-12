"""Serializadores não expõem campos de workflow para escrita direta."""
from copy import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador


class ModeloValidado(serializers.ModelSerializer):
    def validate(self, attrs):
        instancia = copy(self.instance) if self.instance is not None else self.Meta.model()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        try:
            instancia.full_clean(exclude=self._campos_gerados(instancia))
        except DjangoValidationError as erro:
            if hasattr(erro, "message_dict"):
                raise serializers.ValidationError(erro.message_dict) from erro
            raise serializers.ValidationError(erro.messages) from erro
        return attrs

    def _campos_gerados(self, instancia):
        return []


class CompetenciaSerializer(ModeloValidado):
    def validate(self, attrs):
        if self.instance is None and attrs.get("estado", CompetenciaColeta.Estado.ABERTA) != CompetenciaColeta.Estado.ABERTA:
            raise serializers.ValidationError("A competência deve ser criada aberta.")
        return super().validate(attrs)

    class Meta:
        model = CompetenciaColeta
        fields = ("id", "mes", "versao", "estado", "criada_em")
        read_only_fields = ("id", "criada_em")


class AutorizacaoSerializer(ModeloValidado):
    class Meta:
        model = AutorizacaoColeta
        fields = ("id", "usuario", "unidade", "distrito")
        read_only_fields = ("id",)


class RegistroSerializer(ModeloValidado):
    class Meta:
        model = RegistroIndicador
        fields = (
            "id", "competencia", "indicador", "categoria", "unidade", "distrito",
            "dados", "fonte", "observacoes", "situacao", "registrado_por",
            "homologado_por", "motivo_devolucao", "criado_em", "atualizado_em",
            "enviado_em", "decidido_em",
        )
        read_only_fields = (
            "id", "situacao", "registrado_por", "homologado_por", "motivo_devolucao",
            "criado_em", "atualizado_em", "enviado_em", "decidido_em",
        )

    def _campos_gerados(self, instancia):
        # O autor é definido no servidor no perform_create, não pelo cliente.
        return ["registrado_por"] if instancia.registrado_por_id is None else []

    def validate(self, attrs):
        if self.instance is not None:
            protegidos = {"competencia", "indicador", "categoria", "unidade", "distrito"}
            if protegidos & set(attrs):
                raise serializers.ValidationError(
                    "Depois de criado, altere somente dados, fonte ou observações."
                )
        return super().validate(attrs)
