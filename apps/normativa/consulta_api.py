"""Catálogo CAM para consulta do Configurador, sem alterar regras ou pesos."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao
from .models import Indicador, PesoIndicador, RegraIndicador, VersaoNormativa


def permitir_consulta(usuario):
    if not usuario_tem_permissao(usuario, "acesso.gerenciar_competencia"):
        raise PermissionDenied("Consulta normativa reservada ao Configurador.")


class VersoesConsultaView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        permitir_consulta(request.user)
        versoes = VersaoNormativa.objects.order_by("codigo")
        return Response([{"id": v.pk, "codigo": v.codigo, "titulo": v.titulo,
                          "referencia_documental": v.referencia_documental,
                          "vigencia_inicio": v.vigencia_inicio, "vigencia_fim": v.vigencia_fim}
                         for v in versoes])


class VersaoDetalheView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        permitir_consulta(request.user)
        versao = get_object_or_404(VersaoNormativa, pk=pk)
        indicadores = list(Indicador.objects.filter(versao=versao).order_by("ordem", "codigo", "id"))
        regras = list(RegraIndicador.objects.filter(indicador__versao=versao).select_related("categoria", "indicador"))
        pesos = list(PesoIndicador.objects.filter(indicador__versao=versao).select_related("categoria", "indicador"))
        return Response({
            "id": versao.id, "codigo": versao.codigo, "titulo": versao.titulo,
            "referencia_documental": versao.referencia_documental, "observacoes": versao.observacoes,
            "indicadores": [{"id": i.pk, "codigo": i.codigo, "nome": i.nome,
                             "descricao": i.descricao, "pai_id": i.pai_id, "ordem": i.ordem} for i in indicadores],
            "regras": [{"id": r.pk, "indicador_id": r.indicador_id,
                        "categoria": r.categoria.codigo, "categoria_id": r.categoria_id,
                        "metodo": r.metodo, "meta": str(r.meta_valor) if r.meta_valor is not None else None,
                        "unidade": r.meta_unidade, "formula": r.formula_descritiva,
                        "fonte": r.fonte_dados, "observacoes": r.observacoes,
                        "status": (r.parametros or {}).get("status", "NÃO DEFINIDO")}
                       for r in regras],
            "pesos": [{"indicador_id": p.indicador_id, "categoria": p.categoria.codigo,
                       "peso": str(p.peso)} for p in pesos],
        })
