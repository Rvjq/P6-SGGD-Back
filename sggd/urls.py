from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.acesso.urls")),
    path("api/cadastro/", include("apps.cadastro.urls")),
    path("api/coleta/", include("apps.coleta.urls")),
]