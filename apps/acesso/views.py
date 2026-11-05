import json
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import (
    csrf_protect,
    ensure_csrf_cookie,
)
from django.views.decorators.http import (
    require_GET,
    require_POST,
)


@ensure_csrf_cookie
@require_GET
def csrf_view(request):
    return JsonResponse({"detail": "CSRF configurado."})


@csrf_protect
@require_POST
def login_view(request):
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"detail": "JSON inválido."},
            status=400,
        )

    if not isinstance(dados, dict):
        return JsonResponse(
            {"detail": "Formato de dados inválido."},
            status=400,
        )

    email = dados.get("email")
    senha = dados.get("password")

    usuario = authenticate(
        request,
        email=email,
        password=senha,
    )

    if usuario is None:
        return JsonResponse(
            {"detail": "E-mail ou senha inválidos."},
            status=401,
        )

    login(request, usuario)

    return JsonResponse({
        "id": usuario.pk,
        "email": usuario.email,
        "nome": usuario.get_full_name() or usuario.email,
    })

@require_GET
def me_view(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Usuário não autenticado."},
            status=401,
        )

    usuario = request.user

    return JsonResponse({
        "id": usuario.pk,
        "email": usuario.email,
        "nome": usuario.get_full_name() or usuario.email,
        "papeis": list(
            usuario.groups.values_list("name", flat=True)
        ),
        "permissoes": sorted(usuario.get_all_permissions()),
    })

@csrf_protect
@require_POST
def logout_view(request):
    logout(request)

    return JsonResponse({
        "detail": "Sessão encerrada com sucesso."
    })