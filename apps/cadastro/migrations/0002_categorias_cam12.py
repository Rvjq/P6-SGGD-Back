"""Dados iniciais conhecidos da CAM 1.2: oito distritos e 11 categorias.

Não cria unidades ou pessoas fictícias. A operação reversa é propositalmente
noop: categorias e distritos usados em avaliações não devem ser apagados.
"""

from django.db import migrations


CATEGORIAS = (
    ("USF", "Unidade de Saúde da Família", "UNIDADE"),
    ("UBT", "Unidade Básica Tradicional", "UNIDADE"),
    ("UBT_MISTA", "Unidade Básica Tradicional Mista", "UNIDADE"),
    ("CAPS", "Centro de Atenção Psicossocial", "UNIDADE"),
    ("CECON", "Centro de Convivência em Saúde Mental", "UNIDADE"),
    ("UCIS", "Unidade de Cuidado Integral em Saúde", "UNIDADE"),
    ("MAC", "Média e Alta Complexidade", "UNIDADE"),
    ("GG", "Gerente Geral de Distrito Sanitário", "DISTRITO"),
    ("SNA", "Supervisor de Distrito Sanitário — Nível A", "DISTRITO"),
    ("SNB1", "Supervisor de Atenção e Vigilância — Nível B1", "DISTRITO"),
    ("SNB2", "Supervisor de Gestão de Pessoas, Administrativo e Financeiro — Nível B2", "DISTRITO"),
)


TIPOS = (
    ("USF", "Unidade de Saúde da Família", "USF"),
    ("UBT", "Unidade Básica Tradicional", "UBT"),
    ("UBT_MISTA", "Unidade Básica Tradicional Mista", "UBT_MISTA"),
    ("CAPS", "Centro de Atenção Psicossocial", "CAPS"),
    ("CECON", "Centro de Convivência em Saúde Mental", "CECON"),
    ("UCIS", "Unidade de Cuidado Integral em Saúde", "UCIS"),
    ("MAC", "Média e Alta Complexidade", "MAC"),
)


DISTRITOS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")


def carregar_cadastros_iniciais(apps, schema_editor):
    banco = schema_editor.connection.alias
    Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
    Tipo = apps.get_model("cadastro", "TipoUnidade")
    Distrito = apps.get_model("cadastro", "Distrito")

    for codigo, nome, escopo in CATEGORIAS:
        Categoria.objects.using(banco).get_or_create(
            codigo=codigo, defaults={"nome": nome, "escopo": escopo}
        )

    for codigo, nome, categoria_codigo in TIPOS:
        categoria = Categoria.objects.using(banco).get(codigo=categoria_codigo)
        Tipo.objects.using(banco).get_or_create(
            codigo=codigo, defaults={"nome": nome, "categoria_id": categoria.pk}
        )

    for codigo in DISTRITOS:
        Distrito.objects.using(banco).get_or_create(
            codigo=codigo, defaults={"nome": f"Distrito Sanitário {codigo}"}
        )


class Migration(migrations.Migration):
    dependencies = [("cadastro", "0001_initial")]

    operations = [
        migrations.RunPython(carregar_cadastros_iniciais, migrations.RunPython.noop),
    ]
