# Inicial da Coleta; dependências somente de componentes já migrados.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("cadastro", "0002_categorias_cam12"),
        ("normativa", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="CompetenciaColeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mes", models.DateField(unique=True, verbose_name="competência (primeiro dia do mês)")),
                ("estado", models.CharField(choices=[("ABERTA", "Aberta para lançamentos"), ("FECHADA", "Fechada para lançamentos")], default="ABERTA", max_length=8)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("versao", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="competencias_coleta", to="normativa.versaonormativa")),
            ],
            options={"ordering": ("-mes",), "verbose_name": "competência de coleta", "verbose_name_plural": "competências de coleta"},
        ),
        migrations.CreateModel(
            name="AutorizacaoColeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unidade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="autorizacoes_coleta", to="cadastro.unidade")),
                ("distrito", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="autorizacoes_coleta", to="cadastro.distrito")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="autorizacoes_coleta", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("usuario_id", "unidade_id", "distrito_id"),
                "verbose_name": "autorização de coleta", "verbose_name_plural": "autorizações de coleta",
                "constraints": [
                    models.CheckConstraint(condition=(Q(unidade__isnull=False) & Q(distrito__isnull=True)) | (Q(unidade__isnull=True) & Q(distrito__isnull=False)), name="coleta_autorizacao_um_escopo"),
                    models.UniqueConstraint(fields=("usuario", "unidade"), name="coleta_autorizacao_usuario_unidade_unica"),
                    models.UniqueConstraint(fields=("usuario", "distrito"), name="coleta_autorizacao_usuario_distrito_unica"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RegistroIndicador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dados", models.JSONField(default=dict, help_text='Objeto JSON, ex.: {"numerador": 18, "denominador": 20}. Não é nota calculada.', verbose_name="dados aferidos")),
                ("fonte", models.CharField(max_length=255, verbose_name="fonte dos dados")),
                ("observacoes", models.TextField(blank=True)),
                ("situacao", models.CharField(choices=[("RASCUNHO", "Rascunho"), ("ENVIADO", "Enviado para homologação"), ("HOMOLOGADO", "Homologado"), ("DEVOLVIDO", "Devolvido para correção")], default="RASCUNHO", max_length=12)),
                ("motivo_devolucao", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("enviado_em", models.DateTimeField(blank=True, null=True)),
                ("decidido_em", models.DateTimeField(blank=True, null=True)),
                ("categoria", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registros_coleta", to="cadastro.categoriaavaliacao")),
                ("competencia", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registros", to="coleta.competenciacoleta")),
                ("distrito", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="registros_coleta", to="cadastro.distrito")),
                ("homologado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="registros_coleta_analisados", to=settings.AUTH_USER_MODEL)),
                ("indicador", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registros_coleta", to="normativa.indicador")),
                ("registrado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registros_coleta_criados", to=settings.AUTH_USER_MODEL)),
                ("unidade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="registros_coleta", to="cadastro.unidade")),
            ],
            options={
                "ordering": ("-competencia__mes", "indicador__codigo", "id"),
                "verbose_name": "registro de indicador", "verbose_name_plural": "registros de indicadores",
                "constraints": [
                    models.CheckConstraint(condition=(Q(unidade__isnull=False) & Q(distrito__isnull=True)) | (Q(unidade__isnull=True) & Q(distrito__isnull=False)), name="coleta_registro_um_escopo"),
                    models.UniqueConstraint(fields=("competencia", "indicador", "categoria", "unidade"), name="coleta_registro_unidade_unico"),
                    models.UniqueConstraint(fields=("competencia", "indicador", "categoria", "distrito"), name="coleta_registro_distrito_unico"),
                ],
            },
        ),
    ]
