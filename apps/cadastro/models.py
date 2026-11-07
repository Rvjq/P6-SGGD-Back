"""Estrutura e pessoas avaliadas pelo SGGD (recorte CAM 1.2).

Categorias de avaliação não são Groups/papéis de login. As regras e os
pesos pertencem ao app normativa; o cadastro guarda apenas a realidade
organizacional e as designações com vigência.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Distrito(models.Model):
    codigo = models.CharField("código", max_length=10, unique=True)
    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ("codigo",)
        verbose_name = "distrito sanitário"
        verbose_name_plural = "distritos sanitários"

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class CategoriaAvaliacao(models.Model):
    """Categoria da matriz de pesos: 7 de unidade e 4 distritais."""

    class Escopo(models.TextChoices):
        UNIDADE = "UNIDADE", "Unidade"
        DISTRITO = "DISTRITO", "Distrito"

    codigo = models.CharField("código", max_length=20, unique=True)
    nome = models.CharField(max_length=150)
    escopo = models.CharField(max_length=8, choices=Escopo.choices)

    class Meta:
        ordering = ("escopo", "codigo")
        verbose_name = "categoria de avaliação"
        verbose_name_plural = "categorias de avaliação"

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class TipoUnidade(models.Model):
    """Tipo operacional que aponta para uma categoria da matriz CAM 1.2."""

    codigo = models.CharField("código", max_length=30, unique=True)
    nome = models.CharField(max_length=150)
    categoria = models.ForeignKey(
        CategoriaAvaliacao,
        on_delete=models.PROTECT,
        related_name="tipos_unidade",
    )

    class Meta:
        ordering = ("nome",)
        verbose_name = "tipo de unidade"
        verbose_name_plural = "tipos de unidade"

    def clean(self):
        super().clean()
        if self.categoria_id and self.categoria.escopo != CategoriaAvaliacao.Escopo.UNIDADE:
            raise ValidationError({"categoria": "O tipo deve apontar para uma categoria de unidade."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class Unidade(models.Model):
    codigo = models.CharField("código", max_length=40, unique=True)
    nome = models.CharField(max_length=180)
    tipo = models.ForeignKey(TipoUnidade, on_delete=models.PROTECT, related_name="unidades")
    distrito = models.ForeignKey(Distrito, on_delete=models.PROTECT, related_name="unidades")
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ("nome", "codigo")
        verbose_name = "unidade de saúde"
        verbose_name_plural = "unidades de saúde"

    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class PessoaAvaliada(models.Model):
    """Beneficiário potencial: não equivale necessariamente a um usuário de login."""

    codigo = models.CharField("identificador", max_length=40, unique=True)
    nome = models.CharField(max_length=180)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pessoa_avaliada",
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ("nome", "codigo")
        verbose_name = "pessoa avaliada"
        verbose_name_plural = "pessoas avaliadas"

    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class Responsabilidade(models.Model):
    """Designação de uma pessoa para uma unidade OU distrito em um período.

    Pessoas com várias unidades possuem várias linhas. O vínculo distrital
    NÃO replica uma linha por unidade subordinada.
    """

    pessoa = models.ForeignKey(
        PessoaAvaliada, on_delete=models.PROTECT, related_name="responsabilidades"
    )
    categoria = models.ForeignKey(
        CategoriaAvaliacao, on_delete=models.PROTECT, related_name="responsabilidades"
    )
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, null=True, blank=True,
        related_name="responsabilidades",
    )
    distrito = models.ForeignKey(
        Distrito, on_delete=models.PROTECT, null=True, blank=True,
        related_name="responsabilidades",
    )
    data_inicio = models.DateField("início da designação")
    data_fim = models.DateField("fim da designação", null=True, blank=True)
    referencia_designacao = models.CharField(
        "referência do ato de designação", max_length=120, blank=True
    )

    class Meta:
        ordering = ("-data_inicio", "pessoa_id")
        verbose_name = "responsabilidade"
        verbose_name_plural = "responsabilidades"
        constraints = [
            models.CheckConstraint(
                condition=Q(data_fim__isnull=True) | Q(data_fim__gte=F("data_inicio")),
                name="cadastro_resp_periodo_valido",
            ),
            models.CheckConstraint(
                condition=(Q(unidade__isnull=False) & Q(distrito__isnull=True))
                | (Q(unidade__isnull=True) & Q(distrito__isnull=False)),
                name="cadastro_resp_um_escopo",
            ),
            models.UniqueConstraint(
                fields=("pessoa", "categoria", "unidade", "data_inicio"),
                name="cadastro_resp_unidade_inicio_unico",
            ),
            models.UniqueConstraint(
                fields=("pessoa", "categoria", "distrito", "data_inicio"),
                name="cadastro_resp_distrito_inicio_unico",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}

        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "A data final não pode ser anterior à inicial."

        # Exatamente um destino, compatível com o escopo da categoria.
        if (self.unidade_id is None) == (self.distrito_id is None):
            erros["unidade"] = "Informe uma unidade OU um distrito."
            erros["distrito"] = "Informe uma unidade OU um distrito."
        elif self.categoria_id:
            escopo = self.categoria.escopo
            if escopo == CategoriaAvaliacao.Escopo.UNIDADE and not self.unidade_id:
                erros["categoria"] = "Essa categoria exige uma unidade."
            if escopo == CategoriaAvaliacao.Escopo.DISTRITO and not self.distrito_id:
                erros["categoria"] = "Essa categoria exige um distrito."

        # Mesma pessoa/categoria/destino não pode ter designações sobrepostas.
        if (
            not erros
            and self.pessoa_id
            and self.categoria_id
            and self.data_inicio
        ):
            filtros = {
                "pessoa_id": self.pessoa_id,
                "categoria_id": self.categoria_id,
                "unidade_id" if self.unidade_id else "distrito_id": (
                    self.unidade_id if self.unidade_id else self.distrito_id
                ),
            }
            existentes = type(self).objects.filter(**filtros).exclude(pk=self.pk)
            existentes = existentes.filter(
                Q(data_fim__isnull=True) | Q(data_fim__gte=self.data_inicio)
            )
            if self.data_fim is not None:
                existentes = existentes.filter(data_inicio__lte=self.data_fim)
            if existentes.exists():
                erros["data_inicio"] = (
                    "Já existe uma designação sobreposta para essa pessoa, "
                    "categoria e unidade/distrito."
                )

        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        destino = self.unidade if self.unidade_id else self.distrito
        return f"{self.pessoa} — {self.categoria.codigo} — {destino}"
