"""Autorização operacional de Coleta, isolada dos papéis de login."""
from django.db.models import Q

from apps.acesso.interface import usuario_tem_permissao

from .models import AutorizacaoColeta


def pode_lancar(usuario, *, unidade=None, distrito=None):
    if not usuario_tem_permissao(usuario, "acesso.registrar_resultado"):
        return False
    if usuario.is_superuser:
        return True
    autorizacoes = AutorizacaoColeta.objects.filter(usuario=usuario)
    if unidade is not None:
        return autorizacoes.filter(Q(unidade=unidade) | Q(distrito_id=unidade.distrito_id)).exists()
    if distrito is not None:
        return autorizacoes.filter(distrito=distrito).exists()
    return False
