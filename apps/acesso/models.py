from django.contrib.auth.models import AbstractUser
from django.db.models.functions import Lower
from django.db import models

class Usuario(AbstractUser):
    """Usuário do SGGD, identificado pelo e-mail.

    Papéis são representados por Groups do Django e
    operações por Permissions. Um usuário pode exercer
    múltiplos papéis.
    """

    email = models.EmailField(
        "endereço de e-mail",
        blank=False,
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="acesso_usuario_email_unico_ci",
            ),
            models.CheckConstraint(
                condition=~models.Q(email=""),
                name="acesso_usuario_email_obrigatorio",
            ),
        ]

class Operacao(models.Model):
    """Catálogo das operações protegidas do SGGD.

    Não tem tabela: existe só para declarar as Permissions ("acesso.<codename>")
    que os componentes exigem nas suas views e services. A operação em si é
    implementada pelo componente dono (indicado em cada item).
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            # Técnico
            ("registrar_resultado", "Registrar resultados dos indicadores (UC01, coleta)"),
            # Configurador
            ("cadastrar_indicador", "Cadastrar indicadores (UC02, normativa)"),
            ("configurar_regra_calculo", "Configurar regras de cálculo dos indicadores (UC02, normativa)"),
            ("cadastrar_unidade", "Cadastrar unidades avaliadas (cadastro)"),
            ("cadastrar_avaliado", "Cadastrar avaliados e vinculá-los à unidade (cadastro)"),
            # CAM/SECOGE
            ("homologar_resultado", "Conferir e homologar ou devolver resultados (UC03, apuracao)"),
            ("encerrar_ciclo", "Encerrar o ciclo de avaliação (apuracao)"),
            ("publicar_resultado", "Publicar o resultado (UC04, publicacao)"),
            ("julgar_recurso", "Julgar recursos (UC05, recurso)"),
            ("enviar_resultado_folha", "Enviar resultados aprovados para a folha (UC06, pagamento)"),
            # Avaliado
            ("consultar_propria_pontuacao", "Consultar a própria pontuação (UC07, publicacao)"),
            ("apresentar_recurso", "Apresentar recurso (UC08, recurso)"),
        ]
