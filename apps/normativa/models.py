"""Catálogo de regras da avaliação CAM 1.2 (etapa 1: estrutura).

Não há cálculo de notas neste app. Um indicador pode ter filhos de qualquer
profundidade. Metas e métodos são definidos por categoria de avaliação, e
pesos podem existir tanto na matriz principal quanto em subindicadores.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class VersaoNormativa(models.Model):
    """Referência documental para um conjunto fechado de regras de avaliação."""

    codigo = models.CharField("código", max_length=30, unique=True)
    titulo = models.CharField("título", max_length=160)
    referencia_documental = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    vigencia_inicio = models.DateField(null=True, blank=True)
    vigencia_fim = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("codigo",)
        verbose_name = "versão normativa"
        verbose_name_plural = "versões normativas"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(vigencia_fim__isnull=True)
                    | Q(vigencia_inicio__isnull=True)
                    | Q(vigencia_fim__gte=F("vigencia_inicio"))
                ),
                name="normativa_versao_periodo_valido",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.vigencia_inicio is not None
            and self.vigencia_fim is not None
            and self.vigencia_fim < self.vigencia_inicio
        ):
            raise ValidationError({"vigencia_fim": "O fim não pode anteceder o início da vigência."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} — {self.titulo}"


class Indicador(models.Model):
    """Indicador raiz, variante, subindicador ou subdivisão de qualquer nível."""

    versao = models.ForeignKey(
        VersaoNormativa, on_delete=models.PROTECT, related_name="indicadores"
    )
    codigo = models.CharField("código", max_length=35)
    nome = models.CharField(max_length=250)
    descricao = models.TextField(blank=True)
    pai = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="filhos"
    )
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("versao_id", "ordem", "codigo")
        verbose_name = "indicador / subindicador"
        verbose_name_plural = "indicadores / subindicadores"
        constraints = [
            models.UniqueConstraint(
                fields=("versao", "codigo"), name="normativa_indicador_codigo_versao_unico"
            ),
        ]

    def clean(self):
        super().clean()
        if self.pai_id is None:
            return

        if self.pk is not None and self.pai_id == self.pk:
            raise ValidationError({"pai": "Um indicador não pode ser seu próprio pai."})

        # Impede que um filho aponte para outra versão ou crie ciclos.
        ancestral = self.pai
        visitados = set()
        while ancestral is not None:
            if self.versao_id and ancestral.versao_id != self.versao_id:
                raise ValidationError({"pai": "O pai deve pertencer à mesma versão normativa."})
            if ancestral.pk is not None:
                if ancestral.pk == self.pk or ancestral.pk in visitados:
                    raise ValidationError({"pai": "A hierarquia de indicadores não admite ciclos."})
                visitados.add(ancestral.pk)
            ancestral = ancestral.pai

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class RegraIndicador(models.Model):
    """Meta e descrição do método para um indicador em uma categoria CAM.

    Apenas armazena parâmetros; os serviços de apuração interpretarão as regras
    em etapa posterior. A versão é obtida por indicador.versao.
    """

    class Metodo(models.TextChoices):
        NAO_CONFIGURADO = "NAO_CONFIGURADO", "Ainda não configurado"
        NOTA_INFORMADA = "NOTA_INFORMADA", "Nota informada"
        PROPORCAO = "PROPORCAO", "Proporção"
        FAIXAS = "FAIXAS", "Faixas de pontuação"
        MEDIA = "MEDIA", "Média simples"
        MEDIA_PONDERADA = "MEDIA_PONDERADA", "Média ponderada"
        ESPECIFICO = "ESPECIFICO", "Regra específica"

    class Comparador(models.TextChoices):
        MAIOR_IGUAL = "MAIOR_IGUAL", "Maior ou igual a"
        MENOR_IGUAL = "MENOR_IGUAL", "Menor ou igual a"
        IGUAL = "IGUAL", "Igual a"

    class Periodicidade(models.TextChoices):
        NAO_DEFINIDA = "NAO_DEFINIDA", "Não definida"
        MENSAL = "MENSAL", "Mensal"
        BIMESTRAL = "BIMESTRAL", "Bimestral"
        OUTRA = "OUTRA", "Outra"

    indicador = models.ForeignKey(
        Indicador, on_delete=models.PROTECT, related_name="regras"
    )
    categoria = models.ForeignKey(
        "cadastro.CategoriaAvaliacao", on_delete=models.PROTECT, related_name="regras_indicadores"
    )
    metodo = models.CharField(max_length=24, choices=Metodo.choices, default=Metodo.NAO_CONFIGURADO)
    meta_valor = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    meta_comparador = models.CharField(max_length=14, choices=Comparador.choices, blank=True)
    meta_unidade = models.CharField(max_length=30, blank=True)
    periodicidade = models.CharField(
        max_length=14, choices=Periodicidade.choices, default=Periodicidade.NAO_DEFINIDA
    )
    formula_descritiva = models.TextField(blank=True)
    parametros = models.JSONField(default=dict, blank=True)
    fonte_dados = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ("indicador_id", "categoria_id")
        verbose_name = "regra de indicador"
        verbose_name_plural = "regras de indicadores"
        constraints = [
            models.UniqueConstraint(
                fields=("indicador", "categoria"), name="normativa_regra_indicador_categoria_unica"
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}
        if not isinstance(self.parametros, dict):
            erros["parametros"] = "Informe um objeto JSON de parâmetros, não uma lista ou valor isolado."
        if self.meta_valor is None and self.meta_comparador:
            erros["meta_comparador"] = "O comparador requer uma meta numérica."
        if self.meta_valor is not None and not self.meta_comparador:
            erros["meta_comparador"] = "Informe como a meta deve ser comparada."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.indicador.codigo} — {self.categoria.codigo}"


class PesoIndicador(models.Model):
    """Peso (%) por indicador e categoria.

    Se o indicador não tem pai, representa sua parcela no resultado final.
    Se tem pai, representa sua parcela na composição do indicador pai.
    O significado exato e a soma esperada serão verificados na importação.
    """

    indicador = models.ForeignKey(
        Indicador, on_delete=models.PROTECT, related_name="pesos"
    )
    categoria = models.ForeignKey(
        "cadastro.CategoriaAvaliacao", on_delete=models.PROTECT, related_name="pesos_indicadores"
    )
    peso = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Percentual de 0 a 100; ex.: 20,000 significa 20%.",
    )

    class Meta:
        ordering = ("categoria_id", "indicador_id")
        verbose_name = "peso de indicador"
        verbose_name_plural = "pesos de indicadores"
        constraints = [
            models.UniqueConstraint(
                fields=("indicador", "categoria"), name="normativa_peso_indicador_categoria_unico"
            ),
            models.CheckConstraint(
                condition=Q(peso__gte=0) & Q(peso__lte=100),
                name="normativa_peso_entre_zero_cem",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.categoria.codigo} / {self.indicador.codigo}: {self.peso}%"
