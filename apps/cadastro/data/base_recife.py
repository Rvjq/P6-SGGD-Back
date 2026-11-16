"""Valores de referência da estrutura utilizada pela CAM 1.2 em Recife.

Fonte: migração cadastro/0002_categorias_cam12.py e matriz CAM 1.2 importada.
Não representa inventário real de unidades de saúde da Prefeitura.
Diferenciar esses dados oficiais/de referência dos estabelecimentos [DEMO].
"""

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

TIPOS_UNIDADE = (
    ("USF", "Unidade de Saúde da Família", "USF"),
    ("UBT", "Unidade Básica Tradicional", "UBT"),
    ("UBT_MISTA", "Unidade Básica Tradicional Mista", "UBT_MISTA"),
    ("CAPS", "Centro de Atenção Psicossocial", "CAPS"),
    ("CECON", "Centro de Convivência em Saúde Mental", "CECON"),
    ("UCIS", "Unidade de Cuidado Integral em Saúde", "UCIS"),
    ("MAC", "Média e Alta Complexidade", "MAC"),
)

DISTRITOS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")
CATEGORIAS_DISTRITAIS = ("GG", "SNA", "SNB1", "SNB2")

# Prefixo deliberadamente distinto do cadastro real; não criar usuários automáticos.
PREFIXO_DEMO = "DEMO-REC-"
MARCADOR_DESIGNACAO_DEMO = "DEMO_SGGD_RECIFE"
