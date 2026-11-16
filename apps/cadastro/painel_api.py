"""Consulta gerencial da estrutura do SGGD, restrita ao Configurador.

Não cria novas entidades: usa o Cadastro e exibe designações sobrepostas ao mês
solicitado, sem presumir um gestor único quando houver mais de um vínculo.
"""
from calendar import monthrange
from datetime import date

from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao
from .models import CategoriaAvaliacao, Distrito, PessoaAvaliada, Responsabilidade, TipoUnidade, Unidade


def mes_referencia(valor):
    if not valor:
        hoje = date.today()
        return date(hoje.year, hoje.month, 1)
    try:
        inicio = date.fromisoformat(f"{valor}-01")
    except (TypeError, ValueError):
        raise serializers.ValidationError({"mes": "Use AAAA-MM."}) from None
    return inicio


class PainelCadastroView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        if not usuario_tem_permissao(request.user, "acesso.cadastrar_unidade") or not usuario_tem_permissao(request.user, "acesso.cadastrar_avaliado"):
            raise PermissionDenied("Consulta reservada ao Configurador.")
        inicio = mes_referencia(request.query_params.get("mes"))
        fim = date(inicio.year, inicio.month, monthrange(inicio.year, inicio.month)[1])
        distritos = list(Distrito.objects.all().order_by("codigo"))
        unidades = list(Unidade.objects.select_related("tipo__categoria", "distrito").order_by("nome", "id"))
        avaliados = list(PessoaAvaliada.objects.all().order_by("nome"))
        responsabilidades = list(Responsabilidade.objects.select_related("pessoa", "categoria").filter(
            pessoa__ativa=True, data_inicio__lte=fim,
        ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=inicio)))
        por_unidade, por_distrito = {}, {}
        for resp in responsabilidades:
            destino = por_unidade if resp.unidade_id else por_distrito
            chave = resp.unidade_id if resp.unidade_id else resp.distrito_id
            destino.setdefault(chave, []).append({
                "id": resp.id, "pessoa_id": resp.pessoa_id, "pessoa": resp.pessoa.nome,
                "categoria": resp.categoria.codigo,
                "categoria_nome": resp.categoria.nome,
                "inicio": resp.data_inicio.isoformat(),
                "fim": resp.data_fim.isoformat() if resp.data_fim else None,
            })
        return Response({
            "mes": inicio.strftime("%Y-%m"),
            "distritos": [{"id": d.id, "codigo": d.codigo, "nome": d.nome, "ativo": d.ativo,
                           "responsaveis": por_distrito.get(d.id, []),
                           "total_unidades": sum(1 for u in unidades if u.distrito_id == d.id)} for d in distritos],
            "unidades": [{"id": u.id, "codigo": u.codigo, "nome": u.nome, "ativa": u.ativa,
                          "tipo": u.tipo.nome, "tipo_id": u.tipo_id, "categoria": u.tipo.categoria.codigo,
                          "distrito_id": u.distrito_id, "distrito": u.distrito.nome,
                          "responsaveis": por_unidade.get(u.id, [])} for u in unidades],
            "avaliados": [{"id": a.id, "codigo": a.codigo, "nome": a.nome, "ativa": a.ativa} for a in avaliados],
            "categorias": list(CategoriaAvaliacao.objects.order_by("escopo", "codigo").values("id", "codigo", "nome", "escopo")),
            "tipos_unidade": list(TipoUnidade.objects.order_by("nome").values("id", "codigo", "nome", "categoria_id")),
        })
