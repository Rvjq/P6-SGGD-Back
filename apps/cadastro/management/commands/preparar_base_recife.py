"""Ponto único de preparação da base Recife / CAM 1.2.

O catálogo e regras normativas continuam pertencendo a apps.normativa, e são
carregados pelos importadores já validados; este comando apenas os orquestra.
Não cria unidades reais, pessoas, logins, nem dados fictícios.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...data.base_recife import CATEGORIAS, DISTRITOS, TIPOS_UNIDADE
from ...models import CategoriaAvaliacao, Distrito, TipoUnidade


def _inicializar_estrutura(*, atualizar_rotulos=False):
    """Idempotente. Em conflito estrutural, aborta sem substituir dados."""
    contagem = {"categorias": 0, "tipos": 0, "distritos": 0, "rotulos": 0}
    categorias = {}

    for codigo, nome, escopo in CATEGORIAS:
        categoria, criada = CategoriaAvaliacao.objects.get_or_create(
            codigo=codigo, defaults={"nome": nome, "escopo": escopo},
        )
        if categoria.escopo != escopo:
            raise CommandError(
                f"Conflito estrutural: categoria {codigo} está no escopo "
                f"{categoria.escopo!r}, mas a CAM 1.2 exige {escopo!r}. "
                "Corrija manualmente antes de executar novamente."
            )
        if atualizar_rotulos and categoria.nome != nome:
            categoria.nome = nome
            categoria.save(update_fields=["nome"])
            contagem["rotulos"] += 1
        contagem["categorias"] += int(criada)
        categorias[codigo] = categoria

    for codigo, nome, cat_codigo in TIPOS_UNIDADE:
        categoria = categorias[cat_codigo]
        tipo, criado = TipoUnidade.objects.get_or_create(
            codigo=codigo, defaults={"nome": nome, "categoria": categoria},
        )
        if tipo.categoria_id != categoria.pk:
            raise CommandError(
                f"Conflito estrutural: tipo {codigo} aponta para "
                f"{tipo.categoria.codigo}, deveria apontar para {cat_codigo}."
            )
        if atualizar_rotulos and tipo.nome != nome:
            tipo.nome = nome
            tipo.save(update_fields=["nome"])
            contagem["rotulos"] += 1
        contagem["tipos"] += int(criado)

    for codigo in DISTRITOS:
        nome = f"Distrito Sanitário {codigo}"
        distrito, criado = Distrito.objects.get_or_create(
            codigo=codigo, defaults={"nome": nome},
        )
        # Não altera se o distrito estiver inativo nem seu nome sem opção explícita.
        if atualizar_rotulos and distrito.nome != nome:
            distrito.nome = nome
            distrito.save(update_fields=["nome"])
            contagem["rotulos"] += 1
        contagem["distritos"] += int(criado)

    return contagem


class Command(BaseCommand):
    help = (
        "Prepara toda a base Recife: 8 distritos, 11 categorias, 7 tipos, "
        "catálogo CAM 1.2, pesos e regras. Não gera dados fictícios."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Simula a preparação completa e faz rollback de TODAS as alterações.",
        )
        parser.add_argument(
            "--atualizar-rotulos", action="store_true",
            help="Restaura os nomes padrão de categorias, tipos e distritos existentes."
        )
        parser.add_argument(
            "--apenas-estrutura", action="store_true",
            help="Prepara somente distritos, categorias e tipos (sem a Normativa).",
        )

    def handle(self, *args, **options):
        # A atomicidade cobre inclusive a execução dos dois comandos delegados.
        with transaction.atomic():
            numeros = _inicializar_estrutura(atualizar_rotulos=options["atualizar_rotulos"])
            self.stdout.write(
                "ESTRUTURA Recife: 8 distritos, 11 categorias, 7 tipos. "
                f"Novos: {numeros['distritos']} distritos, "
                f"{numeros['categorias']} categorias, {numeros['tipos']} tipos. "
                f"Rótulos atualizados: {numeros['rotulos']}."
            )
            if not options["apenas_estrutura"]:
                # Não duplica a lógica CAM 1.2: reutiliza os importadores existentes,
                # que validam o JSON e falham em conflitos sem sobrescrever o banco.
                self.stdout.write("CATÁLOGO: importar_cam12")
                call_command("importar_cam12", stdout=self.stdout, stderr=self.stderr)
                self.stdout.write("REGRAS: configurar_regras_cam12")
                call_command("configurar_regras_cam12", stdout=self.stdout, stderr=self.stderr)

            if options["dry_run"]:
                transaction.set_rollback(True)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "SIMULAÇÃO concluída: nenhuma alteração foi gravada no banco."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Base Recife preparada. Pode executar novamente: não duplica dados."
            ))
        self.stdout.write(
            "ATENÇÃO: regras marcadas REVISAR não estão liberadas para cálculo automático. "
            "Este comando não cria unidades reais, pessoas nem contas de usuário."
        )
