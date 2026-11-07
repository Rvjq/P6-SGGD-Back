"""Esquema inicial do acesso: usuário customizado e catálogo de operações.

Arquivo pensado para uma INSTALAÇÃO NOVA. Não aplicar em banco com o histórico
antigo do componente acesso.
"""

import django.contrib.auth.models
import django.contrib.auth.validators
import django.utils.timezone
from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Usuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(error_messages={"unique": "A user with that username already exists."}, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.", max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name="username")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(max_length=254, verbose_name="endereço de e-mail")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={
                "verbose_name": "usuário",
                "verbose_name_plural": "usuários",
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(Lower("email"), name="acesso_usuario_email_unico_ci"),
                    models.CheckConstraint(condition=~models.Q(email=""), name="acesso_usuario_email_obrigatorio"),
                ],
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Operacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": [
                    ("cadastrar_indicador", "Cadastrar indicadores"),
                    ("cadastrar_meta", "Cadastrar metas de indicadores"),
                    ("configurar_regra_calculo", "Configurar regras de cálculo e pesos"),
                    ("gerenciar_competencia", "Gerenciar competências de avaliação"),
                    ("cadastrar_unidade", "Cadastrar unidades avaliadas"),
                    ("cadastrar_avaliado", "Cadastrar avaliados e vínculos"),
                    ("registrar_resultado", "Registrar e enviar resultados para homologação"),
                    ("homologar_resultado", "Homologar resultados ou devolver para correção"),
                    ("consultar_resultados", "Consultar resultados dentro do escopo autorizado"),
                    ("apresentar_recurso", "Apresentar recurso sobre a própria avaliação"),
                    ("encerrar_ciclo", "Encerrar ciclo de avaliação"),
                    ("publicar_resultado", "Publicar resultados homologados"),
                    ("julgar_recurso", "Julgar recursos apresentados"),
                    ("enviar_resultado_folha", "Enviar resultados aprovados à folha"),
                ],
            },
        ),
    ]
