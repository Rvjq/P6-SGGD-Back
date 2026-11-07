"""Admin básico para inspecionar e testar os modelos da Normativa."""

from django.contrib import admin

from .models import Indicador, PesoIndicador, RegraIndicador, VersaoNormativa


@admin.register(VersaoNormativa)
class VersaoNormativaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "titulo", "vigencia_inicio", "vigencia_fim")
    search_fields = ("codigo", "titulo", "referencia_documental")


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "versao", "pai", "ordem")
    list_filter = ("versao",)
    list_select_related = ("versao", "pai")
    search_fields = ("codigo", "nome")
    autocomplete_fields = ("pai",)


@admin.register(RegraIndicador)
class RegraIndicadorAdmin(admin.ModelAdmin):
    list_display = ("indicador", "categoria", "metodo", "meta_valor", "periodicidade")
    list_filter = ("categoria", "metodo", "periodicidade")
    list_select_related = ("indicador", "categoria")
    search_fields = ("indicador__codigo", "indicador__nome", "categoria__codigo")
    autocomplete_fields = ("indicador", "categoria")


@admin.register(PesoIndicador)
class PesoIndicadorAdmin(admin.ModelAdmin):
    list_display = ("categoria", "indicador", "peso")
    list_filter = ("categoria", "indicador__versao")
    list_select_related = ("indicador", "categoria")
    search_fields = ("indicador__codigo", "indicador__nome", "categoria__codigo")
    autocomplete_fields = ("indicador", "categoria")
