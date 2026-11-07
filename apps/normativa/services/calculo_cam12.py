"""Cálculos determinísticos dos formatos presentes na CAM 1.2.

O serviço não executa código informado em JSON e não consulta o banco.
A configuração é preparada pela Normativa, mas a coleta de dados e a
homologação pertencem a componentes distintos.

IMPORTANTE: regras marcadas REVISAR não produzem notas por padrão.
"""
from decimal import Decimal, InvalidOperation


class RegraPendente(ValueError):
    """Falta validação da CAM, definição de entradas ou regra inequívoca."""


def decimal(valor, campo="valor"):
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f"{campo} deve ser numérico.")
    try:
        resultado = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as erro:
        raise ValueError(f"{campo} deve ser numérico.") from erro
    if not resultado.is_finite():
        raise ValueError(f"{campo} não pode ser infinito/NaN.")
    return resultado


def nota_percentual(numerador, denominador):
    """Transforma numerador/denominador em porcentagem, com validação."""
    n, d = decimal(numerador, "numerador"), decimal(denominador, "denominador")
    if d <= 0:
        raise ValueError("Denominador deve ser maior que zero; trate exceções normativas explicitamente.")
    if n < 0 or n > d:
        raise ValueError("Numerador deve ficar entre zero e denominador.")
    return n / d * 100


def nota_por_faixas(valor, faixas):
    """Faixas [min,max) com último limite superior aberto."""
    v = decimal(valor)
    if v < 0:
        raise ValueError("Valor não pode ser negativo.")
    for faixa in faixas:
        minimo = decimal(faixa["min"], "min")
        maximo = faixa.get("max")
        if v >= minimo and (maximo is None or v < decimal(maximo, "max")):
            return decimal(faixa["nota"], "nota")
    raise RegraPendente(f"Não há faixa para o valor {v}.")


def media(notas):
    lista = [decimal(x, "nota") for x in notas]
    if not lista:
        raise ValueError("Média exige ao menos uma nota.")
    if any(x < 0 for x in lista):
        raise ValueError("Notas não podem ser negativas.")
    return sum(lista) / len(lista)


def media_ponderada(notas, pesos):
    ns = [decimal(n, "nota") for n in notas]
    ps = [decimal(p, "peso") for p in pesos]
    if len(ns) == 0 or len(ns) != len(ps):
        raise ValueError("Notas e pesos devem ter a mesma quantidade positiva.")
    if any(n < 0 for n in ns) or any(p < 0 for p in ps) or sum(ps) != 100:
        raise ValueError("Notas não negativas e pesos somando 100 são obrigatórios.")
    return sum(n * p for n, p in zip(ns, ps)) / 100


def _obter_notas(dados, codigos=None):
    notas = dados.get("notas")
    if isinstance(notas, dict):
        if codigos is None:
            raise ValueError("Configuração deve declarar códigos quando as notas forem um mapa.")
        faltantes = [c for c in codigos if c not in notas]
        if faltantes:
            raise ValueError(f"Faltam notas para: {', '.join(faltantes)}")
        return [notas[c] for c in codigos]
    if isinstance(notas, (list, tuple)):
        if codigos and len(notas) != len(codigos):
            raise ValueError("Quantidade de notas difere da lista de subindicadores.")
        return notas
    raise ValueError("Informe 'notas' como lista ou como mapa de códigos.")


def _indice_esf(dados, parametros):
    equipes = dados.get("equipes")
    if not isinstance(equipes, (list, tuple)) or not equipes:
        raise ValueError("O Desempenho ESF exige notas de pelo menos uma equipe.")
    codigos = parametros["subindicadores"]
    p1 = parametros["pesos_primeiro_grupo"]
    p2 = parametros["pesos_segundo_grupo"]
    if len(codigos) != 11 or len(p1) != 7 or len(p2) != 4:
        raise ValueError("A composição da ESF exige 7 + 4 itens.")
    notas_equipes = []
    for equipe in equipes:
        if not isinstance(equipe, dict):
            raise ValueError("Notas da equipe devem ser identificadas por subindicador.")
        if any(c not in equipe for c in codigos):
            raise ValueError("Faltam subindicadores em uma equipe.")
        grupo1 = media_ponderada([equipe[c] for c in codigos[:7]], p1)
        grupo2 = media_ponderada([equipe[c] for c in codigos[7:]], p2)
        notas_equipes.append(media_ponderada([grupo1, grupo2], [parametros["peso_grupo_1"], parametros["peso_grupo_2"]]))
    return media(notas_equipes)


def calcular(regra, dados, *, permitir_pendente=False):
    """Avalia configuração parametrizada; não executa expressões arbitrárias.

    regra: dict com 'parametros' e 'meta_valor', ou objeto RegraIndicador.
    dados: entrada de cálculo já aferida/validada pela origem.
    """
    params = regra["parametros"] if isinstance(regra, dict) else regra.parametros
    meta = regra.get("meta_valor") if isinstance(regra, dict) else regra.meta_valor
    status = params.get("status")
    if status == "REVISAR" and not permitir_pendente:
        raise RegraPendente("Regra divergente/incompleta: exige validação da CAM antes do cálculo.")
    op = params.get("operador")
    if op == "nao_configurado":
        raise RegraPendente("Fórmula não configurada com segurança a partir da documentação.")
    if not isinstance(dados, dict):
        raise ValueError("Os dados de entrada devem ser um mapa.")
    if op in ("proporcao", "proporcao_faixas"):
        valor = nota_percentual(dados["numerador"], dados["denominador"])
        return nota_por_faixas(valor, params["faixas"]) if op == "proporcao_faixas" else valor
    if op == "faixas":
        return nota_por_faixas(dados["valor"], params["faixas"])
    if op == "meta":
        if meta is None or decimal(meta) <= 0:
            raise RegraPendente("Meta positiva necessária para calcular o alcance.")
        if "numerador" in dados or "denominador" in dados:
            if "numerador" not in dados or "denominador" not in dados:
                raise ValueError("Informe numerador e denominador juntos.")
            den = decimal(dados["denominador"], "denominador")
            num = decimal(dados["numerador"], "numerador")
            if den == 0 and num == 0:
                excecao = params.get("denominador_zero")
                if excecao == "SEM_OBITOS_NOTA_100" and dados.get("sem_ocorrencias_confirmado") is True:
                    return Decimal("100")
                if excecao == "PROCESSOS_ABERTOS_NOTA_ZERO" and dados.get("processos_em_aberto") is True:
                    return Decimal("0")
                raise RegraPendente("Denominador zero exige comprovação de exceção normativa.")
            valor = nota_percentual(num, den)
        else:
            valor = decimal(dados["valor"])
        if valor < 0:
            raise ValueError("Resultado não pode ser negativo.")
        # NÃO limitar a nota a 100 automaticamente: a Portaria usa resultado/meta
        # e não define teto uniforme para todos os subindicadores.
        return valor / decimal(meta) * 100
    if op == "media":
        return media(_obter_notas(dados, params.get("subindicadores")))
    if op == "media_faixas":
        valor = media(_obter_notas(dados, params.get("subindicadores")))
        return nota_por_faixas(valor, params["faixas"])
    if op == "media_ponderada":
        notas = _obter_notas(dados, params.get("subindicadores"))
        return media_ponderada(notas, params["pesos"])
    if op == "indice_esf":
        return _indice_esf(dados, params)
    if op == "identidade":
        if "nota" in dados:
            return decimal(dados["nota"])
        notas = dados.get("notas", {})
        return decimal(notas[params["origem"]])
    if op == "nota_informada":
        if dados.get("origem_confirmada") is not True:
            raise ValueError("Nota tratada externamente requer origem_confirmada=True.")
        nota = decimal(dados["nota"])
        if nota < 0 or nota > 100:
            raise ValueError("Nota informada deve estar entre 0 e 100.")
        return nota
    raise RegraPendente(f"Operador não suportado ou não definido: {op}")


def consolidar_pontuacao(pesos_por_indicador, notas_por_indicador, *, inaptos=()):
    """Média ponderada da categoria com redistribuição do art. 8º.

    Inaptidão deve ser decisão EXPRESSA da CAM; falta de dado não é inaptidão.
    Os pesos são da matriz 1.2 (44 registros), e não dos subindicadores.
    """
    excluidos = set(inaptos)
    pesos = {c: decimal(p, "peso") for c, p in pesos_por_indicador.items()}
    if sum(pesos.values()) != 100 or any(p < 0 for p in pesos.values()):
        raise ValueError("Os pesos principais cadastrados precisam somar 100%.")
    if not excluidos.issubset(pesos):
        raise ValueError("Indicador inábil desconhecido.")
    restantes = {c: p for c, p in pesos.items() if c not in excluidos}
    if not restantes or sum(restantes.values()) == 0:
        raise RegraPendente("Não é possível redistribuir com todos os indicadores inaptos.")
    faltantes = restantes.keys() - notas_por_indicador.keys()
    if faltantes:
        raise ValueError("Faltam notas de indicadores não declarados inaptos: " + ", ".join(sorted(faltantes)))
    return sum(decimal(notas_por_indicador[c], "nota") * p for c, p in restantes.items()) / sum(restantes.values())
