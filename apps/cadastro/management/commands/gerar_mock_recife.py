"""Gera estabelecimentos e pessoas avaliadas DEMONSTRATIVOS para testes locais.

Não altera as categorias normativas, não cria login, não cria competência,
não mexe em dados reais nem configura as permissões dos Registradores.
"""

from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from ...data.base_recife import (
    CATEGORIAS_DISTRITAIS, DISTRITOS, MARCADOR_DESIGNACAO_DEMO,
    PREFIXO_DEMO, TIPOS_UNIDADE,
)
from ...models import CategoriaAvaliacao, Distrito, PessoaAvaliada, Responsabilidade, TipoUnidade, Unidade


def _criar_pessoa(codigo, nome, numeros):
    pessoa, criada = PessoaAvaliada.objects.get_or_create(
        codigo=codigo, defaults={"nome": nome, "ativa": True},
    )
    if pessoa.nome != nome or pessoa.usuario_id is not None:
        raise CommandError(
            f"Identificador de DEMO já usado ou alterado: {codigo}. "
            "Não alterarei pessoas ou usuários existentes."
        )
    numeros["pessoas"] += int(criada)
    return pessoa


def _criar_responsabilidade(*, pessoa, categoria, unidade=None, distrito=None,
                            inicio, numeros):
    # Não gerar vínculo de demonstração quando houver alguém REAL associado
    # à mesma categoria e ao mesmo local, ainda que somente em mês posterior.
    escopo = {"unidade": unidade} if unidade is not None else {"distrito": distrito}
    outras = Responsabilidade.objects.filter(
        categoria=categoria, **escopo,
    ).exclude(referencia_designacao=MARCADOR_DESIGNACAO_DEMO)
    outras = outras.filter(Q(data_fim__isnull=True) | Q(data_fim__gte=inicio))
    if outras.exists():
        numeros["vinculos_ignorados"] += 1
        return

    filtros = {
        "pessoa": pessoa,
        "categoria": categoria,
        "unidade": unidade,
        "distrito": distrito,
        "referencia_designacao": MARCADOR_DESIGNACAO_DEMO,
    }
    atual = Responsabilidade.objects.filter(**filtros).first()
    if atual:
        if atual.data_fim is not None:
            raise CommandError(
                f"Vínculo de demonstração encerrado para {pessoa.codigo}. "
                "Não vou reabri-lo ou alterar sua vigência automaticamente."
            )
        return

    Responsabilidade.objects.create(**filtros, data_inicio=inicio)
    numeros["responsabilidades"] += 1


class Command(BaseCommand):
    help = (
        "Cria unidades fictícias e avaliados fictícios por unidade/distrito, "
        "sem login e sem alterar a Normativa ou os registros reais."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--unidades-por-tipo", type=int, default=3, metavar="N",
            help="Número de unidades DEMO para cada um dos 7 tipos (1 a 20; padrão: 3).",
        )
        parser.add_argument(
            "--inicio", default="2026-01-01", metavar="AAAA-MM-DD",
            help="Data inicial dos vínculos DEMO (padrão: 2026-01-01).",
        )
        parser.add_argument(
            "--sem-distritais", action="store_true",
            help="Não criar os quatro responsáveis fictícios em cada distrito.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Simula as inserções e desfaz todas as alterações.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Massa fictícia bloqueada porque DJANGO_DEBUG não está ativado. "
                "Execute apenas em ambiente local de desenvolvimento."
            )
        quantidade = options["unidades_por_tipo"]
        if not 1 <= quantidade <= 20:
            raise CommandError("Use --unidades-por-tipo entre 1 e 20.")
        try:
            inicio = date.fromisoformat(options["inicio"])
        except (ValueError, TypeError):
            raise CommandError("A data de --inicio deve estar em AAAA-MM-DD.") from None

        tipos = {x.codigo: x for x in TipoUnidade.objects.select_related("categoria")}
        distritos = {x.codigo: x for x in Distrito.objects.all()}
        categorias = {x.codigo: x for x in CategoriaAvaliacao.objects.all()}
        ausentes = ([x[0] for x in TIPOS_UNIDADE if x[0] not in tipos]
                    + [x for x in DISTRITOS if x not in distritos]
                    + [x for x in CATEGORIAS_DISTRITAIS if x not in categorias])
        if ausentes:
            raise CommandError(
                "Estrutura Recife incompleta (" + ", ".join(ausentes) + "). "
                "Execute primeiro: python manage.py preparar_base_recife"
            )
        for codigo, _nome, categoria_codigo in TIPOS_UNIDADE:
            if tipos[codigo].categoria.codigo != categoria_codigo:
                raise CommandError(f"Tipo {codigo} não corresponde à categoria {categoria_codigo}.")

        numeros = {"unidades": 0, "pessoas": 0, "responsabilidades": 0,
                   "vinculos_ignorados": 0}
        with transaction.atomic():
            for tipo_indice, (tipo_codigo, _nome, _categoria) in enumerate(TIPOS_UNIDADE):
                tipo = tipos[tipo_codigo]
                for numero in range(1, quantidade + 1):
                    codigo = f"{PREFIXO_DEMO}U-{tipo_codigo}-{numero:02d}"
                    nome = f"{tipo_codigo} demonstrativa {numero:02d} [DEMO]"
                    # Distribui sequencialmente pelos 8 distritos, sem fingir que
                    # são estabelecimentos reais de Recife.
                    codigo_distrito = DISTRITOS[
                        (tipo_indice * 5 + numero - 1) % len(DISTRITOS)
                    ]
                    distrito = distritos[codigo_distrito]
                    unidade, criada = Unidade.objects.get_or_create(
                        codigo=codigo,
                        defaults={"nome": nome, "tipo": tipo,
                                  "distrito": distrito, "ativa": True},
                    )
                    if (unidade.nome != nome or unidade.tipo_id != tipo.pk
                            or unidade.distrito_id != distrito.pk):
                        raise CommandError(
                            f"Colisão ou alteração detectada no código DEMO {codigo}. "
                            "Nada será sobrescrito."
                        )
                    numeros["unidades"] += int(criada)

                    codigo_pessoa = f"{PREFIXO_DEMO}P-U-{tipo_codigo}-{numero:02d}"
                    # Não cria um segundo responsável se a unidade já possuir
                    # alguém real; nesses casos tampouco cria pessoa sem vínculo.
                    outras = Responsabilidade.objects.filter(
                        categoria=tipo.categoria, unidade=unidade,
                    ).exclude(referencia_designacao=MARCADOR_DESIGNACAO_DEMO)
                    outras = outras.filter(Q(data_fim__isnull=True) | Q(data_fim__gte=inicio))
                    if outras.exists():
                        numeros["vinculos_ignorados"] += 1
                        continue

                    pessoa = _criar_pessoa(
                        codigo_pessoa,
                        f"Pessoa teste - {tipo_codigo} {numero:02d} [DEMO]",
                        numeros,
                    )
                    _criar_responsabilidade(
                        pessoa=pessoa, categoria=tipo.categoria,
                        unidade=unidade, inicio=inicio, numeros=numeros,
                    )

            if not options["sem_distritais"]:
                for distrito_codigo in DISTRITOS:
                    distrito = distritos[distrito_codigo]
                    for categoria_codigo in CATEGORIAS_DISTRITAIS:
                        categoria = categorias[categoria_codigo]
                        if categoria.escopo != CategoriaAvaliacao.Escopo.DISTRITO:
                            raise CommandError(f"Categoria distrital inválida: {categoria_codigo}.")
                        outras = Responsabilidade.objects.filter(
                            categoria=categoria, distrito=distrito,
                        ).exclude(referencia_designacao=MARCADOR_DESIGNACAO_DEMO)
                        outras = outras.filter(Q(data_fim__isnull=True) | Q(data_fim__gte=inicio))
                        if outras.exists():
                            numeros["vinculos_ignorados"] += 1
                            continue
                        pessoa = _criar_pessoa(
                            f"{PREFIXO_DEMO}P-D-{distrito_codigo}-{categoria_codigo}",
                            f"Pessoa teste - Distrito {distrito_codigo} {categoria_codigo} [DEMO]",
                            numeros,
                        )
                        _criar_responsabilidade(
                            pessoa=pessoa, categoria=categoria,
                            distrito=distrito, inicio=inicio, numeros=numeros,
                        )

            if options["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'SIMULAÇÃO' if options['dry_run'] else 'MOCK RECIFE'}: "
            f"novas unidades={numeros['unidades']}; pessoas={numeros['pessoas']}; "
            f"responsabilidades={numeros['responsabilidades']}; "
            f"vínculos reais preservados={numeros['vinculos_ignorados']}."
        ))
        if options["dry_run"]:
            self.stdout.write("Nenhum dado fictício foi persistido.")
        self.stdout.write(
            "Todos os registros criados são fictícios e marcados [DEMO]. "
            "Nenhuma conta, Registrador, autorização ou competência foi criada."
        )
