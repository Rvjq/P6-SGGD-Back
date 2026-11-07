"""Interface pública do Cadastro para os futuros componentes do SGGD.

O app apuracao poderá consultar designações por competência usando esta
interface, sem importar os modelos internos de cadastro diretamente.
"""

from django.db.models import Q

from .models import Responsabilidade, Unidade


def responsabilidades_na_data(pessoa_id, data_referencia):
    """Designações efetivas para a pessoa em uma data (início/fim inclusivos)."""
    return Responsabilidade.objects.filter(
        pessoa_id=pessoa_id,
        data_inicio__lte=data_referencia,
    ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=data_referencia))


def unidades_do_distrito(distrito_id):
    """Unidades cadastradas atualmente no distrito.

    Atenção: isso NÃO é um histórico de lotação; apuração encerrada precisará
    preservar um snapshot das unidades e regras usadas na competência.
    """
    return Unidade.objects.filter(distrito_id=distrito_id)
