"""Interface pública da Coleta para o futuro componente Apuração."""
from .models import RegistroIndicador


def registros_homologados(competencia_id):
    """Entradas aprovadas; não calcula notas nem inclui rascunhos."""
    return RegistroIndicador.objects.filter(
        competencia_id=competencia_id,
        situacao=RegistroIndicador.Situacao.HOMOLOGADO,
    ).select_related("indicador", "categoria", "unidade", "distrito")
