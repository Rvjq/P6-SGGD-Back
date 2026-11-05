from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

Usuario = get_user_model()

SENHA = "admin"

CONTAS = [
    ("configurador", "configurador@exemplo.com", "Configurador"),
    ("registrador", "registrador@exemplo.com", "Registrador"),
    ("homologador", "homologador@exemplo.com", "Homologador"),
    ("consultador", "consultador@exemplo.com", "Consultador"),
]

for username, email, papel in CONTAS:
    with transaction.atomic():
        usuario, criado = Usuario.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        if usuario.email != email:
            raise ValueError(
                f"Usuário {username} já possui outro e-mail."
            )

        usuario.is_active = True
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.set_password(SENHA)
        usuario.save()

        grupo = Group.objects.get(name=papel)
        usuario.groups.set([grupo])

    acao = "Criado" if criado else "Atualizado"
    print(f"{acao}: {email} | Papel: {papel}")