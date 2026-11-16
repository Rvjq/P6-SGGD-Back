"""Remove apenas fixtures [DEMO] identificadas, de forma opt-in.

Em caso de referências externas protegidas, a operação inteira é revertida.
Não altera distritos, tipos, categorias, normativa ou contas de usuário.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.deletion import ProtectedError, RestrictedError

from ...data.base_recife import MARCADOR_DESIGNACAO_DEMO, PREFIXO_DEMO
from ...models import PessoaAvaliada, Responsabilidade, Unidade


class Command(BaseCommand):
    help = "Remove unidades, pessoas e vínculos gerados por gerar_mock_recife."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar", action="store_true",
            help="Obrigatório para excluir a massa fictícia (não aceita exclusão implícita).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Apresenta a quantidade de registros candidatos, sem excluir.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Limpeza DEMO disponível somente com DJANGO_DEBUG=1.")
        if not options["confirmar"] and not options["dry_run"]:
            raise CommandError("Use --dry-run para conferir ou --confirmar para remover.")

        pessoas = PessoaAvaliada.objects.filter(codigo__startswith=PREFIXO_DEMO + "P-")
        unidades = Unidade.objects.filter(codigo__startswith=PREFIXO_DEMO + "U-")
        vinculos = Responsabilidade.objects.filter(
            pessoa__in=pessoas, referencia_designacao=MARCADOR_DESIGNACAO_DEMO,
        )
        contagens = {
            "vinculos": vinculos.count(),
            "pessoas": pessoas.count(),
            "unidades": unidades.count(),
        }
        if options["dry_run"]:
            self.stdout.write(
                "SIMULAÇÃO LIMPEZA DEMO: "
                f"{contagens['vinculos']} vínculos, {contagens['pessoas']} pessoas, "
                f"{contagens['unidades']} unidades. Nenhum registro excluído."
            )
            return

        # Se alguém associou uma conta de login à pessoa DEMO, revisão humana
        # é obrigatória; não desfazer essa associação silenciosamente.
        if pessoas.filter(usuario__isnull=False).exists():
            raise CommandError(
                "Há pessoa DEMO associada a usuário de login. "
                "Desvincule/revise essa associação antes da limpeza."
            )
        # Impede apagar pessoa DEMO que ganhou vínculo real depois do seed.
        if Responsabilidade.objects.filter(pessoa__in=pessoas).exclude(
            referencia_designacao=MARCADOR_DESIGNACAO_DEMO
        ).exists():
            raise CommandError(
                "Alguma pessoa DEMO possui responsabilidade não DEMO. "
                "Faça a revisão manual para não perder vínculos reais."
            )
        # Impede apagar unidade DEMO que recebeu responsável real.
        if Responsabilidade.objects.filter(unidade__in=unidades).exclude(
            referencia_designacao=MARCADOR_DESIGNACAO_DEMO
        ).exists():
            raise CommandError(
                "Alguma unidade DEMO possui responsável não DEMO. "
                "Faça a revisão manual para preservar vínculos reais."
            )
        try:
            with transaction.atomic():
                vinculos.delete()
                pessoas.delete()
                unidades.delete()
        except (ProtectedError, RestrictedError) as erro:
            raise CommandError(
                "Existem registros que dependem de dados DEMO (ex.: Coleta). "
                "Nenhum dado foi excluído; revise as dependências antes da limpeza."
            ) from erro

        self.stdout.write(self.style.SUCCESS(
            "LIMPEZA DEMO: removidos apenas os registros identificados. "
            f"Vínculos={contagens['vinculos']}, pessoas={contagens['pessoas']}, "
            f"unidades={contagens['unidades']}. "
            "Distritos, categorias e Normativa foram preservados."
        ))
