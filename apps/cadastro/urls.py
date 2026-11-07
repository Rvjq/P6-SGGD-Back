"""Rotas administrativas de cadastro: /api/cadastro/."""

from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaAvaliacaoViewSet,
    DistritoViewSet,
    PessoaAvaliadaViewSet,
    ResponsabilidadeViewSet,
    TipoUnidadeViewSet,
    UnidadeViewSet,
)

router = DefaultRouter()
router.register("distritos", DistritoViewSet, basename="distrito")
router.register("categorias-avaliacao", CategoriaAvaliacaoViewSet, basename="categoria-avaliacao")
router.register("tipos-unidade", TipoUnidadeViewSet, basename="tipo-unidade")
router.register("unidades", UnidadeViewSet, basename="unidade")
router.register("avaliados", PessoaAvaliadaViewSet, basename="avaliado")
router.register("responsabilidades", ResponsabilidadeViewSet, basename="responsabilidade")

urlpatterns = router.urls
