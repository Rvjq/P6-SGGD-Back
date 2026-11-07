"""API do cadastro: exclusivamente Configurador (ou superusuário técnico).

Ainda não fornece listas globais a Consultadores ou Registradores. Nas futuras
APIs de coleta/consulta, a autorização será resolvida por escopo e competência.
"""

from rest_framework import mixins, viewsets

from apps.acesso.interface import ExigePermissao

from .models import (
    CategoriaAvaliacao,
    Distrito,
    PessoaAvaliada,
    Responsabilidade,
    TipoUnidade,
    Unidade,
)
from .serializers import (
    CategoriaAvaliacaoSerializer,
    DistritoSerializer,
    PessoaAvaliadaSerializer,
    ResponsabilidadeSerializer,
    TipoUnidadeSerializer,
    UnidadeSerializer,
)


class CadastroEditavelViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD sem DELETE e sem PUT; alterações são feitas com PATCH.

    Evita excluir cadastros que possam participar de avaliações históricas.
    """

    permission_classes = (ExigePermissao,)
    http_method_names = ("get", "post", "patch", "head", "options")


class DistritoViewSet(CadastroEditavelViewSet):
    queryset = Distrito.objects.all()
    serializer_class = DistritoSerializer
    permissoes_exigidas = ("acesso.cadastrar_unidade",)


class CategoriaAvaliacaoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CategoriaAvaliacao.objects.all()
    serializer_class = CategoriaAvaliacaoSerializer
    permission_classes = (ExigePermissao,)
    permissoes_exigidas = ("acesso.cadastrar_unidade",)


class TipoUnidadeViewSet(CadastroEditavelViewSet):
    queryset = TipoUnidade.objects.select_related("categoria")
    serializer_class = TipoUnidadeSerializer
    permissoes_exigidas = ("acesso.cadastrar_unidade",)


class UnidadeViewSet(CadastroEditavelViewSet):
    queryset = Unidade.objects.select_related("tipo", "distrito")
    serializer_class = UnidadeSerializer
    permissoes_exigidas = ("acesso.cadastrar_unidade",)

    def get_queryset(self):
        queryset = super().get_queryset()
        distrito = self.request.query_params.get("distrito")
        tipo = self.request.query_params.get("tipo")
        if distrito:
            queryset = queryset.filter(distrito_id=distrito)
        if tipo:
            queryset = queryset.filter(tipo_id=tipo)
        return queryset


class PessoaAvaliadaViewSet(CadastroEditavelViewSet):
    queryset = PessoaAvaliada.objects.select_related("usuario")
    serializer_class = PessoaAvaliadaSerializer
    permissoes_exigidas = ("acesso.cadastrar_avaliado",)


class ResponsabilidadeViewSet(CadastroEditavelViewSet):
    queryset = Responsabilidade.objects.select_related(
        "pessoa", "categoria", "unidade", "distrito"
    )
    serializer_class = ResponsabilidadeSerializer
    permissoes_exigidas = ("acesso.cadastrar_avaliado",)

    def get_queryset(self):
        queryset = super().get_queryset()
        pessoa = self.request.query_params.get("pessoa")
        if pessoa:
            queryset = queryset.filter(pessoa_id=pessoa)
        return queryset
