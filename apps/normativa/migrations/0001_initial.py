# Esquema da Normativa CAM 1.2 (etapa 1). Nenhum indicador é inserido aqui.
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cadastro", "0002_categorias_cam12"),
    ]

    operations = [
        migrations.CreateModel(
            name="VersaoNormativa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=30, unique=True, verbose_name="código")),
                ("titulo", models.CharField(max_length=160, verbose_name="título")),
                ("referencia_documental", models.CharField(blank=True, max_length=255)),
                ("observacoes", models.TextField(blank=True)),
                ("vigencia_inicio", models.DateField(blank=True, null=True)),
                ("vigencia_fim", models.DateField(blank=True, null=True)),
            ],
            options={
                "ordering": ("codigo",),
                "verbose_name": "versão normativa",
                "verbose_name_plural": "versões normativas",
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(vigencia_fim__isnull=True) | Q(vigencia_inicio__isnull=True) | Q(vigencia_fim__gte=F("vigencia_inicio")),
                        name="normativa_versao_periodo_valido",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Indicador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=35, verbose_name="código")),
                ("nome", models.CharField(max_length=250)),
                ("descricao", models.TextField(blank=True)),
                ("ordem", models.PositiveIntegerField(default=0)),
                ("pai", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="filhos", to="normativa.indicador")),
                ("versao", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="indicadores", to="normativa.versaonormativa")),
            ],
            options={
                "ordering": ("versao_id", "ordem", "codigo"),
                "verbose_name": "indicador / subindicador",
                "verbose_name_plural": "indicadores / subindicadores",
                "constraints": [
                    models.UniqueConstraint(fields=("versao", "codigo"), name="normativa_indicador_codigo_versao_unico"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RegraIndicador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("metodo", models.CharField(choices=[
                    ("NAO_CONFIGURADO", "Ainda não configurado"),
                    ("NOTA_INFORMADA", "Nota informada"),
                    ("PROPORCAO", "Proporção"),
                    ("FAIXAS", "Faixas de pontuação"),
                    ("MEDIA", "Média simples"),
                    ("MEDIA_PONDERADA", "Média ponderada"),
                    ("ESPECIFICO", "Regra específica"),
                ], default="NAO_CONFIGURADO", max_length=24)),
                ("meta_valor", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("meta_comparador", models.CharField(blank=True, choices=[
                    ("MAIOR_IGUAL", "Maior ou igual a"),
                    ("MENOR_IGUAL", "Menor ou igual a"),
                    ("IGUAL", "Igual a"),
                ], max_length=14)),
                ("meta_unidade", models.CharField(blank=True, max_length=30)),
                ("periodicidade", models.CharField(choices=[
                    ("NAO_DEFINIDA", "Não definida"),
                    ("MENSAL", "Mensal"),
                    ("BIMESTRAL", "Bimestral"),
                    ("OUTRA", "Outra"),
                ], default="NAO_DEFINIDA", max_length=14)),
                ("formula_descritiva", models.TextField(blank=True)),
                ("parametros", models.JSONField(blank=True, default=dict)),
                ("fonte_dados", models.CharField(blank=True, max_length=255)),
                ("observacoes", models.TextField(blank=True)),
                ("categoria", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="regras_indicadores", to="cadastro.categoriaavaliacao")),
                ("indicador", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="regras", to="normativa.indicador")),
            ],
            options={
                "ordering": ("indicador_id", "categoria_id"),
                "verbose_name": "regra de indicador",
                "verbose_name_plural": "regras de indicadores",
                "constraints": [
                    models.UniqueConstraint(fields=("indicador", "categoria"), name="normativa_regra_indicador_categoria_unica"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PesoIndicador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("peso", models.DecimalField(
                    decimal_places=3, max_digits=6,
                    help_text="Percentual de 0 a 100; ex.: 20,000 significa 20%.",
                    validators=[
                        django.core.validators.MinValueValidator(Decimal("0")),
                        django.core.validators.MaxValueValidator(Decimal("100")),
                    ],
                )),
                ("categoria", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pesos_indicadores", to="cadastro.categoriaavaliacao")),
                ("indicador", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pesos", to="normativa.indicador")),
            ],
            options={
                "ordering": ("categoria_id", "indicador_id"),
                "verbose_name": "peso de indicador",
                "verbose_name_plural": "pesos de indicadores",
                "constraints": [
                    models.UniqueConstraint(fields=("indicador", "categoria"), name="normativa_peso_indicador_categoria_unico"),
                    models.CheckConstraint(
                        condition=Q(peso__gte=0) & Q(peso__lte=100),
                        name="normativa_peso_entre_zero_cem",
                    ),
                ],
            },
        ),
    ]
