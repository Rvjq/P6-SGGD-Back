from django.urls import path

from .views import (
    csrf_view,
    login_view,
    logout_view,
    me_view,
)

from .operadores import OperadoresView, OperadorDetalheView, UsuariosConsultaView

urlpatterns = [
    path("usuarios/", UsuariosConsultaView.as_view(), name="consulta-usuarios"),
    path("operadores/", OperadoresView.as_view(), name="operadores"),
    path("operadores/<int:pk>/", OperadorDetalheView.as_view(), name="operador-detalhe"),
    path("csrf/", csrf_view, name="csrf"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("me/", me_view, name="me"),
]