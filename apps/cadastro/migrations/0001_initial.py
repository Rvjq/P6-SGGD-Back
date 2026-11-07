# Esquema inicial do cadastro estrutural CAM 1.2.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoriaAvaliacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=20, unique=True, verbose_name="código")),
                ("nome", models.CharField(max_length=150)),
                ("escopo", models.CharField(choices=[("UNIDADE", "Unidade"), ("DISTRITO", "Distrito")], max_length=8)),
            ],
            options={
                "ordering": ("escopo", "codigo"),
                "verbose_name": "categoria de avaliação",
                "verbose_name_plural": "categorias de avaliação",
            },
        ),
        migrations.CreateModel(
            name="Distrito",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=10, unique=True, verbose_name="código")),
                ("nome", models.CharField(max_length=120)),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("codigo",),
                "verbose_name": "distrito sanitário",
                "verbose_name_plural": "distritos sanitários",
            },
        ),
        migrations.CreateModel(
            name="PessoaAvaliada",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=40, unique=True, verbose_name="identificador")),
                ("nome", models.CharField(max_length=180)),
                ("ativa", models.BooleanField(default=True)),
                ("usuario", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pessoa_avaliada", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("nome", "codigo"),
                "verbose_name": "pessoa avaliada",
                "verbose_name_plural": "pessoas avaliadas",
            },
        ),
        migrations.CreateModel(
            name="TipoUnidade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=30, unique=True, verbose_name="código")),
                ("nome", models.CharField(max_length=150)),
                ("categoria", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tipos_unidade", to="cadastro.categoriaavaliacao")),
            ],
            options={
                "ordering": ("nome",),
                "verbose_name": "tipo de unidade",
                "verbose_name_plural": "tipos de unidade",
            },
        ),
        migrations.CreateModel(
            name="Unidade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=40, unique=True, verbose_name="código")),
                ("nome", models.CharField(max_length=180)),
                ("ativa", models.BooleanField(default=True)),
                ("distrito", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="unidades", to="cadastro.distrito")),
                ("tipo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="unidades", to="cadastro.tipounidade")),
            ],
            options={
                "ordering": ("nome", "codigo"),
                "verbose_name": "unidade de saúde",
                "verbose_name_plural": "unidades de saúde",
            },
        ),
        migrations.CreateModel(
            name="Responsabilidade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data_inicio", models.DateField(verbose_name="início da designação")),
                ("data_fim", models.DateField(blank=True, null=True, verbose_name="fim da designação")),
                ("referencia_designacao", models.CharField(blank=True, max_length=120, verbose_name="referência do ato de designação")),
                ("categoria", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="responsabilidades", to="cadastro.categoriaavaliacao")),
                ("distrito", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="responsabilidades", to="cadastro.distrito")),
                ("pessoa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="responsabilidades", to="cadastro.pessoaavaliada")),
                ("unidade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="responsabilidades", to="cadastro.unidade")),
            ],
            options={
                "ordering": ("-data_inicio", "pessoa_id"),
                "verbose_name": "responsabilidade",
                "verbose_name_plural": "responsabilidades",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
                        name="cadastro_resp_periodo_valido",
                    ),
                    models.CheckConstraint(
                        condition=(models.Q(unidade__isnull=False) & models.Q(distrito__isnull=True)) | (models.Q(unidade__isnull=True) & models.Q(distrito__isnull=False)),
                        name="cadastro_resp_um_escopo",
                    ),
                    models.UniqueConstraint(fields=("pessoa", "categoria", "unidade", "data_inicio"), name="cadastro_resp_unidade_inicio_unico"),
                    models.UniqueConstraint(fields=("pessoa", "categoria", "distrito", "data_inicio"), name="cadastro_resp_distrito_inicio_unico"),
                ],
            },
        ),
    ]
