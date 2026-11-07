"""Serialização e validação do cadastro na API."""

from copy import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    CategoriaAvaliacao,
    Distrito,
    PessoaAvaliada,
    Responsabilidade,
    TipoUnidade,
    Unidade,
)


class ModeloValidadoSerializer(serializers.ModelSerializer):
    """Executa também as validações cruzadas do modelo antes do salvamento."""

    def validate(self, attrs):
        instancia = copy(self.instance) if self.instance is not None else self.Meta.model()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        try:
            instancia.full_clean()
        except DjangoValidationError as erro:
            if hasattr(erro, "message_dict"):
                raise serializers.ValidationError(erro.message_dict) from erro
            raise serializers.ValidationError(erro.messages) from erro
        return attrs


class DistritoSerializer(ModeloValidadoSerializer):
    class Meta:
        model = Distrito
        fields = ("id", "codigo", "nome", "ativo")
        read_only_fields = ("id",)


class CategoriaAvaliacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaAvaliacao
        fields = ("id", "codigo", "nome", "escopo")


class TipoUnidadeSerializer(ModeloValidadoSerializer):
    class Meta:
        model = TipoUnidade
        fields = ("id", "codigo", "nome", "categoria")
        read_only_fields = ("id",)


class UnidadeSerializer(ModeloValidadoSerializer):
    class Meta:
        model = Unidade
        fields = ("id", "codigo", "nome", "tipo", "distrito", "ativa")
        read_only_fields = ("id",)


class PessoaAvaliadaSerializer(ModeloValidadoSerializer):
    class Meta:
        model = PessoaAvaliada
        fields = ("id", "codigo", "nome", "usuario", "ativa")
        read_only_fields = ("id",)


class ResponsabilidadeSerializer(ModeloValidadoSerializer):
    class Meta:
        model = Responsabilidade
        fields = (
            "id", "pessoa", "categoria", "unidade", "distrito",
            "data_inicio", "data_fim", "referencia_designacao",
        )
        read_only_fields = ("id",)
