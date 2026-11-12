"""Rotas /api/coleta/: ciclos, autorizações, registros e homologação."""
from rest_framework.routers import DefaultRouter

from .views import AutorizacaoViewSet, CompetenciaViewSet, RegistroViewSet

router = DefaultRouter()
router.register("competencias", CompetenciaViewSet, basename="competencia-coleta")
router.register("autorizacoes", AutorizacaoViewSet, basename="autorizacao-coleta")
router.register("registros", RegistroViewSet, basename="registro-coleta")
urlpatterns = router.urls
