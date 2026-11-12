"""Coleta de resultados CAM 1.2, sem cálculo nem publicação.

Uma competência escolhe a versão normativa; um registro descreve dados
brutos ou previamente aferidos de UM indicador e UM escopo. A homologação
valida o registro, não calcula a gratificação.
"""

from django.conf import settings
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class CompetenciaColeta(models.Model):
    class Estado(models.TextChoices):
        ABERTA = "ABERTA", "Aberta para lançamentos"
        FECHADA = "FECHADA", "Fechada para lançamentos"

    mes = models.DateField("competência (primeiro dia do mês)", unique=True)
    versao = models.ForeignKey(
        "normativa.VersaoNormativa", on_delete=models.PROTECT, related_name="competencias_coleta"
    )
    estado = models.CharField(max_length=8, choices=Estado.choices, default=Estado.ABERTA)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-mes",)
        verbose_name = "competência de coleta"
        verbose_name_plural = "competências de coleta"

    def clean(self):
        super().clean()
        erros = {}
        if self.mes and self.mes.day != 1:
            erros["mes"] = "Use o primeiro dia do mês (AAAA-MM-01)."
        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).values("mes", "versao_id").first()
            if anterior and (anterior["mes"] != self.mes or anterior["versao_id"] != self.versao_id):
                erros["mes"] = "A competência e a versão não podem ser alteradas depois de criadas."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mes:%m/%Y} — {self.versao.codigo}"


class AutorizacaoColeta(models.Model):
    """Usuário pode lançar em uma unidade OU em um distrito e suas unidades.

    É autorização operacional, independente de cargos avaliados. Não define
    qual área técnica é responsável por cada indicador (fora do MVP atual).
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="autorizacoes_coleta"
    )
    unidade = models.ForeignKey(
        "cadastro.Unidade", on_delete=models.PROTECT,
        null=True, blank=True, related_name="autorizacoes_coleta",
    )
    distrito = models.ForeignKey(
        "cadastro.Distrito", on_delete=models.PROTECT,
        null=True, blank=True, related_name="autorizacoes_coleta",
    )

    class Meta:
        ordering = ("usuario_id", "unidade_id", "distrito_id")
        verbose_name = "autorização de coleta"
        verbose_name_plural = "autorizações de coleta"
        constraints = [
            models.CheckConstraint(
                condition=(Q(unidade__isnull=False) & Q(distrito__isnull=True))
                | (Q(unidade__isnull=True) & Q(distrito__isnull=False)),
                name="coleta_autorizacao_um_escopo",
            ),
            models.UniqueConstraint(
                fields=("usuario", "unidade"), name="coleta_autorizacao_usuario_unidade_unica"
            ),
            models.UniqueConstraint(
                fields=("usuario", "distrito"), name="coleta_autorizacao_usuario_distrito_unica"
            ),
        ]

    def clean(self):
        super().clean()
        if (self.unidade_id is None) == (self.distrito_id is None):
            raise ValidationError("Selecione uma unidade OU um distrito.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario_id} — {self.unidade or self.distrito}"


class RegistroIndicador(models.Model):
    class Situacao(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ENVIADO = "ENVIADO", "Enviado para homologação"
        HOMOLOGADO = "HOMOLOGADO", "Homologado"
        DEVOLVIDO = "DEVOLVIDO", "Devolvido para correção"

    competencia = models.ForeignKey(
        CompetenciaColeta, on_delete=models.PROTECT, related_name="registros"
    )
    indicador = models.ForeignKey(
        "normativa.Indicador", on_delete=models.PROTECT, related_name="registros_coleta"
    )
    categoria = models.ForeignKey(
        "cadastro.CategoriaAvaliacao", on_delete=models.PROTECT,
        related_name="registros_coleta",
    )
    unidade = models.ForeignKey(
        "cadastro.Unidade", on_delete=models.PROTECT, null=True, blank=True,
        related_name="registros_coleta",
    )
    distrito = models.ForeignKey(
        "cadastro.Distrito", on_delete=models.PROTECT, null=True, blank=True,
        related_name="registros_coleta",
    )
    dados = models.JSONField(
        "dados aferidos", default=dict,
        help_text='Objeto JSON, ex.: {"numerador": 18, "denominador": 20}. Não é nota calculada.',
    )
    fonte = models.CharField("fonte dos dados", max_length=255)
    observacoes = models.TextField(blank=True)
    situacao = models.CharField(
        max_length=12, choices=Situacao.choices, default=Situacao.RASCUNHO
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="registros_coleta_criados",
    )
    homologado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="registros_coleta_analisados",
    )
    motivo_devolucao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-competencia__mes", "indicador__codigo", "id")
        verbose_name = "registro de indicador"
        verbose_name_plural = "registros de indicadores"
        constraints = [
            models.CheckConstraint(
                condition=(Q(unidade__isnull=False) & Q(distrito__isnull=True))
                | (Q(unidade__isnull=True) & Q(distrito__isnull=False)),
                name="coleta_registro_um_escopo",
            ),
            models.UniqueConstraint(
                fields=("competencia", "indicador", "categoria", "unidade"),
                name="coleta_registro_unidade_unico",
            ),
            models.UniqueConstraint(
                fields=("competencia", "indicador", "categoria", "distrito"),
                name="coleta_registro_distrito_unico",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}
        if (self.unidade_id is None) == (self.distrito_id is None):
            erros["unidade"] = "Selecione uma unidade OU um distrito."
        elif self.categoria_id:
            if self.unidade_id:
                if self.categoria.escopo != "UNIDADE" or self.unidade.tipo.categoria_id != self.categoria_id:
                    erros["categoria"] = "A categoria deve ser a categoria CAM da unidade."
            elif self.categoria.escopo != "DISTRITO":
                erros["categoria"] = "Esta categoria exige um registro distrital."

        if self.competencia_id and self.indicador_id:
            if self.indicador.versao_id != self.competencia.versao_id:
                erros["indicador"] = "O indicador deve pertencer à versão da competência."
            elif self.categoria_id:
                Regras = apps.get_model("normativa", "RegraIndicador")
                if not Regras.objects.filter(indicador_id=self.indicador_id, categoria_id=self.categoria_id).exists():
                    erros["categoria"] = "Não há regra CAM para esse indicador e categoria."
            if self.competencia.estado != CompetenciaColeta.Estado.ABERTA and self.situacao in (
                self.Situacao.RASCUNHO, self.Situacao.DEVOLVIDO
            ):
                erros["competencia"] = "Não é permitido editar lançamentos em competência fechada."

        if not isinstance(self.dados, dict) or not self.dados:
            erros["dados"] = "Informe um objeto JSON com pelo menos um campo."
        if not self.fonte or not self.fonte.strip():
            erros["fonte"] = "Informe a fonte dos dados aferidos."
        if self.situacao == self.Situacao.DEVOLVIDO and not self.motivo_devolucao.strip():
            erros["motivo_devolucao"] = "A devolução exige justificativa."
        if self.situacao == self.Situacao.HOMOLOGADO:
            if self.homologado_por_id is None:
                erros["homologado_por"] = "A homologação exige um responsável."
            elif self.homologado_por_id == self.registrado_por_id:
                erros["homologado_por"] = "Quem registrou não pode homologar o próprio registro."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.indicador.codigo} / {self.competencia.mes:%m/%Y} / {self.situacao}"
