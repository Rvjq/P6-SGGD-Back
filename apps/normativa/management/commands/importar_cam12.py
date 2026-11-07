"""Importa apenas catálogo e pesos PRINCIPAIS da CAM 1.2 da planilha SESAU.

Não configura metas, fórmulas, vigência ou pesos internos dos subindicadores.
Não altera nem exclui dados existentes; conflitos interrompem a operação.
"""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import Indicador, PesoIndicador, VersaoNormativa


ARQUIVO = Path(__file__).resolve().parents[2] / "data" / "cam12.json"
CATEGORIAS_ESPERADAS = frozenset(
    {"USF", "UBT", "UBT_MISTA", "CAPS", "CECON", "UCIS", "MAC", "GG", "SNA", "SNB1", "SNB2"}
)
RAIZES_ESPERADAS = frozenset({"1", "2", "3", "4", "5"})


def carregar_e_validar_dados():
    """Faz validação da fonte antes de abrir qualquer transação de escrita."""
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise CommandError(f"Não foi possível ler os dados CAM 1.2: {erro}") from erro

    catalogo = dados.get("catalogo", [])
    matriz = dados.get("pesos_principais", {})
    if dados.get("versao", {}).get("codigo") != "CAM 1.2":
        raise CommandError("O catálogo não corresponde à CAM 1.2.")
    if len(catalogo) != 58 or len({i["codigo"] for i in catalogo}) != 58:
        raise CommandError("Catálogo inválido: esperados 57 registros da planilha e a raiz auxiliar '4'.")
    if frozenset(matriz) != CATEGORIAS_ESPERADAS:
        raise CommandError("Matriz incompleta: devem existir as 11 categorias CAM 1.2.")

    codigos = {item["codigo"] for item in catalogo}
    raizes = {item["codigo"] for item in catalogo if item["pai"] is None}
    if raizes != RAIZES_ESPERADAS:
        raise CommandError("Hierarquia inválida: esperados cinco indicadores principais (1 a 5).")
    if any(item["pai"] not in codigos for item in catalogo if item["pai"]):
        raise CommandError("Há indicadores com pai inexistente no catálogo.")

    for item in catalogo:
        if not item["nome"] or len(item["nome"]) > 250 or len(item["codigo"]) > 35:
            raise CommandError(f"Nome ou código inválido: {item['codigo']}.")
        # A ordem do arquivo deve permitir cadastrar o pai antes do filho.
        if item["pai"] and item["pai"] == item["codigo"]:
            raise CommandError(f"Indicador não pode ser pai de si mesmo: {item['codigo']}.")

    total_pesos = 0
    for categoria, pesos in matriz.items():
        try:
            if not set(pesos).issubset(RAIZES_ESPERADAS):
                raise CommandError(f"Pesos não principais encontrados na matriz de {categoria}.")
            valores = [Decimal(v) for v in pesos.values()]
        except (InvalidOperation, ValueError, TypeError) as erro:
            raise CommandError(f"Peso inválido em {categoria}: {erro}") from erro
        if not valores or any(v < 0 or v > 100 for v in valores):
            raise CommandError(f"Há pesos ausentes ou fora do intervalo em {categoria}.")
        if sum(valores) != Decimal("100"):
            raise CommandError(f"Os pesos principais de {categoria} não somam 100%.")
        total_pesos += len(pesos)
    if total_pesos != 44:
        raise CommandError(f"Matriz incompleta: esperados 44 pesos, encontrados {total_pesos}.")
    return dados


def descricao_de_origem(item):
    """Preserva metadados para conferência, sem ativar subpesos para apuração."""
    linha = item["linha_origem"]
    origem = (
        f"Planilha 'Pesos Subindicadores', linha {linha}"
        if linha is not None
        else "Planilha 'Pesos Indicadores', linha 6 (raiz auxiliar)"
    )
    partes = [
        f"Origem: {origem}.",
        f"Classificação na fonte: {item['tipo_original']}.",
    ]
    if item.get("cargos_descricao_original"):
        partes.append(f"Aplicação indicada na fonte: {item['cargos_descricao_original']}")
    if item["peso_portaria_documentado_pct"] is not None:
        partes.append(
            "Peso interno segundo coluna 'Peso conforme Portaria' da planilha: "
            f"{item['peso_portaria_documentado_pct']}% (não ativado nesta etapa)."
        )
    if item["peso_excepcional_planilha_pct"] is not None:
        partes.append(
            "Peso interno segundo coluna 'Peso atual excepcional' da planilha: "
            f"{item['peso_excepcional_planilha_pct']}% (não ativado nesta etapa)."
        )
    if item["codigo"] == "4.IV.2":
        partes.append(
            "ATENÇÃO: a linha 41 menciona MAC, mas está sob o bloco UCIS na planilha; "
            "exige conferência antes de configurar a regra."
        )
    return "\n".join(partes)


class Command(BaseCommand):
    help = (
        "Importa os 57 registros catalogados na CAM 1.2 (mais raiz 4) e "
        "44 pesos principais da planilha SESAU. Não importa metas/fórmulas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Executa todas as validações, simula a importação e desfaz as mudanças.",
        )

    def handle(self, *args, **options):
        dados = carregar_e_validar_dados()
        Categoria = apps.get_model("cadastro", "CategoriaAvaliacao")
        categorias = {
            categoria.codigo: categoria
            for categoria in Categoria.objects.filter(codigo__in=CATEGORIAS_ESPERADAS)
        }
        faltantes = CATEGORIAS_ESPERADAS - categorias.keys()
        if faltantes:
            raise CommandError(
                "Categorias ausentes no Cadastro: " + ", ".join(sorted(faltantes))
                + ". Verifique as migrações do app cadastro."
            )

        criados = {"versoes": 0, "indicadores": 0, "pesos": 0}
        with transaction.atomic():
            versao, criado = VersaoNormativa.objects.get_or_create(
                codigo="CAM 1.2", defaults=dados["versao"] | {"codigo": "CAM 1.2"}
            )
            criados["versoes"] += int(criado)
            registros = {}
            for ordem, item in enumerate(dados["catalogo"], start=1):
                codigo = item["codigo"]
                codigo_pai = item["pai"]
                if codigo_pai is not None and codigo_pai not in registros:
                    raise CommandError(
                        f"A ordem do catálogo é inválida: '{codigo}' vem antes de '{codigo_pai}'."
                    )
                pai = registros.get(codigo_pai)
                indicador, criado = Indicador.objects.get_or_create(
                    versao=versao,
                    codigo=codigo,
                    defaults={
                        "nome": item["nome"],
                        "pai": pai,
                        "ordem": ordem,
                        "descricao": descricao_de_origem(item),
                    },
                )
                if not criado and (indicador.nome != item["nome"] or indicador.pai_id != (pai.pk if pai else None)):
                    raise CommandError(
                        f"Conflito em CAM 1.2/{codigo}: já existe um indicador com outro nome "
                        "ou outro pai. A importação foi desfeita. Verifique os registros de teste "
                        "no Django Admin; nada será substituído automaticamente."
                    )
                criados["indicadores"] += int(criado)
                registros[codigo] = indicador

            for categoria_codigo, pesos in dados["pesos_principais"].items():
                for codigo_indicador, valor in pesos.items():
                    peso_decimal = Decimal(valor)
                    peso, criado = PesoIndicador.objects.get_or_create(
                        categoria=categorias[categoria_codigo],
                        indicador=registros[codigo_indicador],
                        defaults={"peso": peso_decimal},
                    )
                    if not criado and peso.peso != peso_decimal:
                        raise CommandError(
                            f"Conflito de peso em {categoria_codigo}/{codigo_indicador}: "
                            f"banco={peso.peso}%; fonte={peso_decimal}%. "
                            "A importação foi desfeita; não sobrescrevemos ajustes existentes."
                        )
                    criados["pesos"] += int(criado)

            if options["dry_run"]:
                transaction.set_rollback(True)

        prefixo = "SIMULAÇÃO: " if options["dry_run"] else "IMPORTAÇÃO: "
        self.stdout.write(self.style.SUCCESS(
            prefixo
            + f"CAM 1.2 | 58 indicadores/hierarquia (57 da planilha + raiz 4) | "
            f"44 pesos principais em 11 categorias. "
            f"Novos: {criados['versoes']} versão, {criados['indicadores']} indicadores, "
            f"{criados['pesos']} pesos."
        ))
        if options["dry_run"]:
            self.stdout.write("Nenhuma alteração foi gravada no banco de dados.")
        self.stdout.write(
            "Metas, fórmulas, vigência e pesos internos dos subindicadores NÃO "
            "foram ativados nesta etapa."
        )
