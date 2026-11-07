"""Cria os quatro papéis funcionais e vincula suas permissões mínimas.

Em um banco recém-criado, o Django normalmente cria content types e permissões
pelo sinal post_migrate. Esta migração precisa deles antes do fim de migrate,
então cria/recupera explicitamente as permissões do catálogo Operacao.
"""

from django.db import migrations


PERMISSOES_POR_PAPEL = {
    "Configurador": (
        "cadastrar_indicador",
        "cadastrar_meta",
        "configurar_regra_calculo",
        "gerenciar_competencia",
        "cadastrar_unidade",
        "cadastrar_avaliado",
    ),
    "Registrador": ("registrar_resultado",),
    "Homologador": ("homologar_resultado",),
    "Consultador": ("consultar_resultados", "apresentar_recurso"),
}


def criar_papeis_e_permissoes(apps, schema_editor):
    banco = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Operacao = apps.get_model("acesso", "Operacao")

    content_type, _ = ContentType.objects.using(banco).get_or_create(
        app_label="acesso",
        model="operacao",
    )

    # Obtém o catálogo histórico descrito em 0001 (não importa models.py atual).
    permissoes = {}
    for codigo, descricao in Operacao._meta.permissions:
        permissao, _ = Permission.objects.using(banco).get_or_create(
            content_type=content_type,
            codename=codigo,
            defaults={"name": descricao},
        )
        permissoes[codigo] = permissao

    for nome, codigos in PERMISSOES_POR_PAPEL.items():
        faltantes = set(codigos) - permissoes.keys()
        if faltantes:
            raise RuntimeError(f"Permissões inexistentes no catálogo: {sorted(faltantes)}")

        grupo, _ = Group.objects.using(banco).get_or_create(name=nome)
        grupo.permissions.set([permissoes[codigo] for codigo in codigos])

    # Sem concessão automática de: encerrar_ciclo, publicar_resultado,
    # julgar_recurso e enviar_resultado_folha.


def remover_papeis(apps, schema_editor):
    banco = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    Group.objects.using(banco).filter(name__in=PERMISSOES_POR_PAPEL).delete()
    # Não excluir ContentType/Permission: são gerenciados pelo Django e podem
    # continuar existindo após a reversão desta migração de dados.


class Migration(migrations.Migration):
    dependencies = [
        ("acesso", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(criar_papeis_e_permissoes, remover_papeis),
    ]
