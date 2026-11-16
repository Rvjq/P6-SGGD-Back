from django.urls import path
from .consulta_api import VersoesConsultaView, VersaoDetalheView
urlpatterns = [
    path("versoes/", VersoesConsultaView.as_view(), name="consulta-versoes"),
    path("versoes/<int:pk>/", VersaoDetalheView.as_view(), name="consulta-versao"),
]
