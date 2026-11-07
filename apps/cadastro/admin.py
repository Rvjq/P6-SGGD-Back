"""Cadastro estrutural para uso administrativo no Django Admin."""

from django.contrib import admin

from .models import (
    CategoriaAvaliacao,
    Distrito,
    PessoaAvaliada,
    Responsabilidade,
    TipoUnidade,
    Unidade,
)


@admin.register(Distrito)
class DistritoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("codigo", "nome")


@admin.register(CategoriaAvaliacao)
class CategoriaAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "escopo")
    list_filter = ("escopo",)
    search_fields = ("codigo", "nome")

    def get_readonly_fields(self, request, obj=None):
        # A identidade e o escopo de categorias já usadas não devem mudar.
        return ("codigo", "escopo") if obj else ()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TipoUnidade)
class TipoUnidadeAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "categoria")
    list_select_related = ("categoria",)
    search_fields = ("codigo", "nome")
    autocomplete_fields = ("categoria",)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "tipo", "distrito", "ativa")
    list_select_related = ("tipo", "distrito")
    list_filter = ("ativa", "tipo", "distrito")
    search_fields = ("codigo", "nome")
    autocomplete_fields = ("tipo", "distrito")


@admin.register(PessoaAvaliada)
class PessoaAvaliadaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "usuario", "ativa")
    list_filter = ("ativa",)
    search_fields = ("codigo", "nome")
    autocomplete_fields = ("usuario",)


@admin.register(Responsabilidade)
class ResponsabilidadeAdmin(admin.ModelAdmin):
    list_display = (
        "pessoa", "categoria", "unidade", "distrito",
        "data_inicio", "data_fim", "referencia_designacao",
    )
    list_select_related = ("pessoa", "categoria", "unidade", "distrito")
    list_filter = ("categoria", "distrito", "data_inicio")
    search_fields = ("pessoa__codigo", "pessoa__nome", "referencia_designacao")
    autocomplete_fields = ("pessoa", "categoria", "unidade", "distrito")
