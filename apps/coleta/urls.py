"""API /api/coleta/: competências, atribuições, tarefas e registros."""
from .painel_configurador_api import PainelConfiguradorView
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AutorizacaoViewSet, CompetenciaViewSet, RegistroViewSet
from .tarefas_api import (EnviarTarefaView, OpcoesColetaView, SalvarTarefaView,
                          TarefasColetaView)

from .configuracao_api import ConfiguracaoColetaView
from .revisao_api import RevisaoTarefasView, DecidirTarefaView
from .resumo_api import ResumoColetaView

router = DefaultRouter()
router.register("competencias", CompetenciaViewSet, basename="competencia-coleta")
router.register("autorizacoes", AutorizacaoViewSet, basename="autorizacao-coleta")
router.register("registros", RegistroViewSet, basename="registro-coleta")

urlpatterns = [
    path("painel-configurador/", PainelConfiguradorView.as_view(), name="painel-configurador"),
    path("resumo/", ResumoColetaView.as_view(), name="resumo-coleta"),
    path("configuracao/", ConfiguracaoColetaView.as_view(), name="opcoes-configuracao-coleta"),
    path("tarefas/revisao/", RevisaoTarefasView.as_view(), name="revisao-tarefas-coleta"),
    path("tarefas/decidir/", DecidirTarefaView.as_view(), name="decidir-tarefa-coleta"),
    path("tarefas/", TarefasColetaView.as_view(), name="tarefas-coleta"),
    path("tarefas/salvar/", SalvarTarefaView.as_view(), name="salvar-tarefa-coleta"),
    path("tarefas/enviar/", EnviarTarefaView.as_view(), name="enviar-tarefa-coleta"),
    path("opcoes/", OpcoesColetaView.as_view(), name="opcoes-coleta"),
    *router.urls,
]
