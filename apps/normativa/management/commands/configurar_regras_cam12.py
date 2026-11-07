"""Configura 157 associações de regras da CAM 1.2 sem sobrescrever ajustes existentes.

Executar DEPOIS de importar_cam12. Tem dry-run transacional.
"""
import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import Indicador, RegraIndicador, VersaoNormativa

ARQUIVO = Path(__file__).resolve().parents[2] / "data" / "regras_cam12.json"
CODIGOS_CATEGORIAS = frozenset({"USF", "UBT", "UBT_MISTA", "CAPS", "CECON", "UCIS", "MAC", "GG", "SNA", "SNB1", "SNB2"})
METODOS = frozenset(codigo for codigo, _rotulo in RegraIndicador.Metodo.choices)


def carregar_regras():
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CommandError(f"Falha na leitura de regras CAM 1.2: {e}") from e
    if dados.get("versao") != "CAM 1.2":
        raise CommandError("Arquivo não pertence à CAM 1.2.")
    regras = dados.get("regras")
    if not isinstance(regras, dict) or len(regras) != 58:
        raise CommandError("São esperados os 58 códigos existentes no catálogo CAM 1.2.")
    chave_unica = set()
    for codigo, blocos in regras.items():
        if not isinstance(blocos, list) or not blocos:
            raise CommandError(f"Blocos ausentes no indicador {codigo}.")
        for bloco in blocos:
            if bloco["metodo"] not in METODOS:
                raise CommandError(f"Método incompatível com models.py: {codigo}")
            if not isinstance(bloco["parametros"], dict):
                raise CommandError(f"Parâmetros inválidos: {codigo}")
            for categoria in bloco["categorias"]:
                if categoria not in CODIGOS_CATEGORIAS:
                    raise CommandError(f"Categoria desconhecida: {categoria}")
                chave = (codigo, categoria)
                if chave in chave_unica:
                    raise CommandError(f"Regra duplicada: {codigo}/{categoria}")
                chave_unica.add(chave)
    if len(chave_unica) != 157:
        raise CommandError(f"Esperadas 157 regras e encontradas {len(chave_unica)}.")
    return regras


class Command(BaseCommand):
    help = "Configura métodos, metas e parâmetros CAM 1.2; não sobrescreve regras existentes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simula toda a operação e faz rollback.")

    def handle(self, *args, **options):
        regras = carregar_regras()
        versao = VersaoNormativa.objects.filter(codigo="CAM 1.2").first()
        if versao is None:
            raise CommandError("Execute antes: python manage.py importar_cam12")
        indicadores = {i.codigo: i for i in Indicador.objects.filter(versao=versao)}
        if set(indicadores) != set(regras):
            raise CommandError("Catálogo CAM 1.2 diferente do esperado: confira a importação da Etapa 2.")
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        categorias = {c.codigo:c for c in Categoria.objects.filter(codigo__in=CODIGOS_CATEGORIAS)}
        if set(categorias) != CODIGOS_CATEGORIAS:
            raise CommandError("Faltam categorias da CAM 1.2 no app cadastro.")
        novos = 0
        with transaction.atomic():
            for codigo, blocos in regras.items():
                for bloco in blocos:
                    defaults = {key: bloco[key] for key in (
                        "metodo", "meta_valor", "meta_comparador", "meta_unidade", "periodicidade",
                        "formula_descritiva", "parametros", "fonte_dados", "observacoes",
                    )}
                    for cat in bloco["categorias"]:
                        obj, criado = RegraIndicador.objects.get_or_create(
                            indicador=indicadores[codigo], categoria=categorias[cat], defaults=defaults
                        )
                        if not criado:
                            # Evita apagar alterações do Configurador ou alterar regras já usadas.
                            if any(getattr(obj, campo) != valor for campo, valor in defaults.items()):
                                raise CommandError(
                                    f"Regra já existente e diferente: {codigo}/{cat}. "
                                    "Nenhum registro foi sobrescrito; operação desfeita."
                                )
                        novos += int(criado)
            if options["dry_run"]:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(
            f"{'SIMULAÇÃO' if options['dry_run'] else 'CONFIGURAÇÃO'} CAM 1.2: 157 regras em 58 indicadores, novas={novos}."
        ))
        if options["dry_run"]:
            self.stdout.write("Nenhuma alteração persistida.")
        self.stdout.write("Regras REVISAR não podem ser calculadas automaticamente sem validação institucional.")
