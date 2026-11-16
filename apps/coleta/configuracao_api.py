"""Dados que alimentam as telas de configuração, sem abrir Cadastro para Registradores."""
from django.apps import apps
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from apps.acesso.interface import usuario_tem_permissao


class ConfiguracaoColetaView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        if not usuario_tem_permissao(request.user, "acesso.gerenciar_competencia"):
            raise PermissionDenied("A configuração é reservada ao Configurador.")
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        Unidade = apps.get_model("cadastro", "Unidade")
        Distrito = apps.get_model("cadastro", "Distrito")
        Versao = apps.get_model("normativa", "VersaoNormativa")
        Usuario = apps.get_model("acesso", "Usuario")
        return Response({
            "versoes": list(Versao.objects.order_by("codigo").values("id", "codigo", "titulo")),
            "unidades": [{"id": u.pk, "nome": u.nome, "codigo": u.codigo,
                           "distrito": u.distrito_id, "categoria": u.tipo.categoria.codigo}
                          for u in Unidade.objects.filter(ativa=True, distrito__ativo=True)
                              .select_related("tipo__categoria").order_by("nome", "id")],
            "distritos": list(Distrito.objects.filter(ativo=True).order_by("codigo").values("id", "codigo", "nome")),
            "registradores": list(Usuario.objects.filter(is_active=True, groups__name="Registrador")
                                  .distinct().order_by("email").values("id", "email", "first_name", "last_name")),
            "categorias": list(Categoria.objects.order_by("codigo").values("id", "codigo", "nome", "escopo")),
        })
