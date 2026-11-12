"""Admin: supervisão da Coleta. Registro só é alterado pelo fluxo da API."""
from django.contrib import admin

from .models import AutorizacaoColeta, CompetenciaColeta, RegistroIndicador


@admin.register(CompetenciaColeta)
class CompetenciaColetaAdmin(admin.ModelAdmin):
    list_display = ("mes", "versao", "estado", "criada_em")
    list_filter = ("estado", "versao")
    def get_readonly_fields(self, request, obj=None):
        return ("mes", "versao", "criada_em") if obj else ("criada_em",)
    def has_change_permission(self, request, obj=None):
        # Fechamento somente pela API, que verifica registros pendentes.
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AutorizacaoColeta)
class AutorizacaoColetaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "unidade", "distrito")
    list_filter = ("distrito",)
    autocomplete_fields = ("usuario", "unidade", "distrito")


@admin.register(RegistroIndicador)
class RegistroIndicadorAdmin(admin.ModelAdmin):
    list_display = ("id", "competencia", "indicador", "categoria", "unidade", "distrito", "situacao", "registrado_por")
    list_filter = ("situacao", "competencia", "categoria")
    search_fields = ("indicador__codigo", "fonte", "registrado_por__email")
    readonly_fields = (
        "competencia", "indicador", "categoria", "unidade", "distrito",
        "dados", "fonte", "observacoes", "situacao", "registrado_por",
        "homologado_por", "motivo_devolucao", "criado_em", "atualizado_em",
        "enviado_em", "decidido_em",
    )
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
