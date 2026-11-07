"""Identidade de usuários e catálogo de operações protegidas do SGGD.

Os papéis são Groups do Django; este módulo não cria campo de papel.
O vínculo com pessoas/unidades pertence ao componente de cadastro.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class Usuario(AbstractUser):
    """Usuário do SGGD; login por e-mail é configurado em acesso.backends.

    O campo username permanece interno por compatibilidade com o modelo atual.
    O e-mail deve ser informado e não pode se repetir, ignorando maiúsculas.
    """

    email = models.EmailField("endereço de e-mail", blank=False)

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
    """Catálogo de permissões (acesso.<codename>) sem tabela própria.

    A distribuição inicial das permissões fica em 0002_papeis_e_permissoes.
    Ter uma permissão não dispensa a validação de vínculo e conflito de
    interesse no componente responsável pela operação.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            # Configurador: regras e estrutura da avaliação.
            ("cadastrar_indicador", "Cadastrar indicadores"),
            ("cadastrar_meta", "Cadastrar metas de indicadores"),
            ("configurar_regra_calculo", "Configurar regras de cálculo e pesos"),
            ("gerenciar_competencia", "Gerenciar competências de avaliação"),
            ("cadastrar_unidade", "Cadastrar unidades avaliadas"),
            ("cadastrar_avaliado", "Cadastrar avaliados e vínculos"),
            # Registrador: informa valores alcançados; não define as metas.
            ("registrar_resultado", "Registrar e enviar resultados para homologação"),
            # Homologador: conferência central inicial (CAM/SECOGE).
            ("homologar_resultado", "Homologar resultados ou devolver para correção"),
            # Consultador: o escopo efetivo será verificado pelo backend.
            ("consultar_resultados", "Consultar resultados dentro do escopo autorizado"),
            ("apresentar_recurso", "Apresentar recurso sobre a própria avaliação"),
            # Operações existentes, ainda sem responsável definido.
            ("encerrar_ciclo", "Encerrar ciclo de avaliação"),
            ("publicar_resultado", "Publicar resultados homologados"),
            ("julgar_recurso", "Julgar recursos apresentados"),
            ("enviar_resultado_folha", "Enviar resultados aprovados à folha"),
        ]
