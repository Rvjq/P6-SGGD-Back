"""Tarefas CAM 1.2 derivadas do Cadastro + Normativa, sem registros vazios.

Uma tarefa = indicador principal / unidade (ou origem distrital) / competência.
Os campos são as folhas aplicáveis da árvore de indicadores; nós de agregação
não recebem entrada manual. Nenhum cálculo de nota é realizado aqui.
"""
from collections import defaultdict
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
from django.apps import apps
from django.db.models import Q

from .models import AutorizacaoColeta, RegistroIndicador


OPERADORES_ENTRADA = {"meta", "faixas", "proporcao_faixas", "nota_informada"}


def catalogo_de_campos(regra):
    """Definição de formulário gerada *da regra do banco*, nunca do React.

    Retorna (tipo, campos, aviso). REVISAO desabilita apenas o item afetado.
    """
    p = regra.parametros or {}
    operador = p.get("operador", "nao_configurado")
    situacao = p.get("status", "REVISAR")
    if situacao == "REVISAR" or operador == "nao_configurado":
        return "INDISPONIVEL", [], (
            "Regra de preenchimento/cálculo ainda não validada para este protótipo. "
            "O item não será considerado como zero."
        )
    if operador not in OPERADORES_ENTRADA:
        return "AUTOMATICO", [], "Resultado derivado de outros indicadores, sem lançamento manual."
    if operador == "nota_informada":
        return "PREENCHIMENTO", [{
            "chave": "nota", "rotulo": "Nota aferida", "tipo": "decimal", "unidade": "pontos (0 a 100)",
            "obrigatorio": True,
        }], "Nota obtida na fonte indicada; não calculada pelo SGGD nesta etapa."
    if operador == "proporcao_faixas":
        return "PREENCHIMENTO", [
            {"chave": "numerador", "rotulo": "Quantidade que cumpriu o critério", "tipo": "decimal", "unidade": "quantidade", "obrigatorio": True},
            {"chave": "denominador", "rotulo": "Quantidade total elegível", "tipo": "decimal", "unidade": "quantidade (> 0)", "obrigatorio": True},
        ], "Informe numerador e denominador conforme a fonte indicada."
    return "PREENCHIMENTO", [{
        "chave": "valor", "rotulo": "Resultado aferido", "tipo": "decimal",
        "unidade": regra.meta_unidade or "valor", "obrigatorio": True,
    }], "Informe o valor já aferido pela área responsável, sem calcular a nota aqui."


def validar_dados(campos, dados):
    """Valida forma, não o cálculo de pontuação; exceções ficam para Apuração."""
    if not isinstance(dados, dict):
        raise ValueError("Os dados devem ser um objeto com os campos da tarefa.")
    esperados = {item["chave"] for item in campos}
    if set(dados) != esperados:
        raise ValueError("Campos esperados: " + ", ".join(sorted(esperados)))
    for nome, valor in dados.items():
        if isinstance(valor, bool) or isinstance(valor, (list, dict)) or valor is None:
            raise ValueError(f"O campo {nome} precisa conter um número.")
        try:
            numero = Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"O campo {nome} precisa conter um número.") from None
        if not numero.is_finite() or numero < 0:
            raise ValueError(f"O campo {nome} precisa ser um número finito não negativo.")
        if nome == "denominador" and numero == 0:
            raise ValueError("O denominador deve ser maior que zero.")
        if nome == "nota" and numero > 100:
            raise ValueError("A nota aferida deve estar entre 0 e 100.")


def escopos_autorizados(usuario):
    """Consulta apenas localidades autorizadas; uma atribuição distrital cobre unidades."""
    Unidade = apps.get_model("cadastro", "Unidade")
    Distrito = apps.get_model("cadastro", "Distrito")
    if usuario.is_superuser:
        return (list(Unidade.objects.filter(ativa=True).select_related("tipo__categoria", "distrito")),
                list(Distrito.objects.filter(ativo=True)))
    autorizacoes = AutorizacaoColeta.objects.filter(usuario=usuario)
    ids_unidades = autorizacoes.exclude(unidade_id=None).values_list("unidade_id", flat=True)
    ids_distritos = autorizacoes.exclude(distrito_id=None).values_list("distrito_id", flat=True)
    unidades = list(Unidade.objects.filter(
        Q(id__in=ids_unidades) | Q(distrito_id__in=ids_distritos), ativa=True, distrito__ativo=True,
    ).select_related("tipo__categoria", "distrito").distinct().order_by("nome", "pk"))
    distritos = list(Distrito.objects.filter(id__in=ids_distritos, ativo=True).order_by("codigo", "pk"))
    return unidades, distritos


def _indices_normativos(competencia):
    Indicador = apps.get_model("normativa", "Indicador")
    Peso = apps.get_model("normativa", "PesoIndicador")
    Regra = apps.get_model("normativa", "RegraIndicador")
    indicadores = list(Indicador.objects.filter(versao=competencia.versao))
    por_codigo = {i.codigo: i for i in indicadores}
    filhos = defaultdict(list)
    for indicador in indicadores:
        filhos[indicador.pai_id].append(indicador)
    for lista in filhos.values():
        lista.sort(key=lambda i: (i.ordem, i.codigo))
    pesos = defaultdict(list)
    for peso in Peso.objects.filter(indicador__versao=competencia.versao, indicador__pai__isnull=True).select_related("indicador"):
        pesos[peso.categoria_id].append((peso.indicador, peso.peso))
    for lista in pesos.values():
        lista.sort(key=lambda par: (par[0].ordem, par[0].codigo))
    regras = {(r.indicador_id, r.categoria_id): r for r in Regra.objects.filter(
        indicador__versao=competencia.versao
    ).select_related("indicador", "categoria")}
    return filhos, pesos, regras


def _campos_arvore(indicador, categoria, filhos, regras, registros, usuario):
    """Expande folhas *com regras da categoria*, ignorando agregadores."""
    filhos_aplicaveis = [i for i in filhos.get(indicador.pk, ()) if (i.pk, categoria.pk) in regras]
    if filhos_aplicaveis:
        resultado = []
        for filho in filhos_aplicaveis:
            resultado.extend(_campos_arvore(filho, categoria, filhos, regras, registros, usuario))
        return resultado
    regra = regras.get((indicador.pk, categoria.pk))
    if regra is None:
        return []
    estado, definicao, aviso = catalogo_de_campos(regra)
    registro = registros.get(indicador.pk)
    terceiro = bool(registro and registro.registrado_por_id != usuario.pk and not usuario.is_superuser)
    if terceiro:
        aviso = "Registro atribuído a outro autor; solicite revisão das atribuições ao Configurador."
    return [{
        "indicador": indicador.pk, "codigo": indicador.codigo, "nome": indicador.nome,
        "tipo": estado, "campos": definicao, "fonte_sugerida": regra.fonte_dados,
        "unidade_medida": regra.meta_unidade, "aviso": aviso,
        "registro_id": registro.pk if registro and not terceiro else None,
        "situacao": ("ATRIBUIDO_A_OUTRO" if terceiro else registro.situacao) if registro else ("INDISPONIVEL" if estado == "INDISPONIVEL" else "PENDENTE"),
        "dados": registro.dados if registro and not terceiro else None,
        "fonte": registro.fonte if registro and not terceiro else "",
        "motivo_devolucao": registro.motivo_devolucao if registro and not terceiro else "",
    }]


def _avisos_de_calculo(indicador, categoria, filhos, regras):
    """Avisos para regras intermediárias ainda não apuráveis."""
    avisos = []
    def visitar(no):
        regra = regras.get((no.pk, categoria.pk))
        if regra is None:
            return
        if filhos.get(no.pk):
            if (regra.parametros or {}).get("status") == "REVISAR":
                avisos.append(
                    f"A fórmula de consolidação de {no.codigo} ainda depende de validação. "
                    "Os dados preenchidos não produzirão nota automaticamente."
                )
            for filho in filhos[no.pk]:
                visitar(filho)
    visitar(indicador)
    return avisos


def _tarefas_do_escopo(competencia, *, unidade=None, distrito=None, categoria=None,
                       filhos=None, pesos=None, regras=None, registros=None, usuario=None, distrito_origem=False):
    if categoria is None:
        categoria = unidade.tipo.categoria
    resultado = []
    for raiz, peso in pesos.get(categoria.pk, []):
        campos = _campos_arvore(raiz, categoria, filhos, regras, registros, usuario)
        # Distritos têm resultados derivados das unidades (I1–I4): não são entradas manuais.
        if distrito_origem and not any(c["tipo"] == "PREENCHIMENTO" for c in campos):
            continue
        if not campos:
            continue
        ativos = [c for c in campos if c["tipo"] == "PREENCHIMENTO"]
        preenchidos = sum(c["situacao"] not in ("PENDENTE", "INDISPONIVEL", "ATRIBUIDO_A_OUTRO") for c in ativos)
        situacoes = {c["situacao"] for c in ativos}
        if not ativos:
            estado = "INDISPONIVEL"
        elif situacoes == {"HOMOLOGADO"}:
            estado = "HOMOLOGADA"
        elif situacoes == {"ENVIADO"}:
            estado = "ENVIADA"
        elif "DEVOLVIDO" in situacoes:
            estado = "DEVOLVIDA"
        elif preenchidos:
            estado = "EM_ANDAMENTO"
        else:
            estado = "NAO_INICIADA"
        resultado.append({
            "indicador": raiz.pk, "codigo": raiz.codigo, "nome": raiz.nome,
            "peso": str(peso), "categoria": categoria.pk, "categoria_codigo": categoria.codigo,
            "unidade": unidade.pk if unidade else None,
            "distrito": distrito.pk if distrito else None,
            "situacao": estado, "campos_total": len(ativos), "campos_preenchidos": preenchidos,
            "avisos_calculo": _avisos_de_calculo(raiz, categoria, filhos, regras),
            "itens": campos,
        })
    return resultado


def gerar_tarefas(competencia, usuario):
    """Retorna escopos com tarefas do usuário, sem criar registros no banco.

    I5 é coletado uma única vez por distrito/competência SOMENTE quando há
    designação vigente de uma categoria que precisa desse indicador segundo
    os pesos da versão normativa. A categoria GG é apenas a referência técnica
    do registro compartilhado, mesmo quando o avaliado elegível é SNA/SNB1.
    """
    unidades, distritos = escopos_autorizados(usuario)
    filhos, pesos, regras = _indices_normativos(competencia)
    Categ = apps.get_model("cadastro", "CategoriaAvaliacao")
    categoria_base = Categ.objects.filter(codigo="GG", escopo="DISTRITO").first()
    # Designações válidas em algum momento do mês. Pessoas podem compartilhar
    # responsabilidades; por isso o retorno é uma lista, nunca um nome suposto.
    Responsabilidade = apps.get_model("cadastro", "Responsabilidade")
    inicio = competencia.mes
    fim = date(inicio.year, inicio.month, monthrange(inicio.year, inicio.month)[1])
    atribuidos = Responsabilidade.objects.filter(
        pessoa__ativa=True, data_inicio__lte=fim,
    ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=inicio)).select_related("pessoa", "categoria")
    por_unidade = defaultdict(list)
    por_distrito = defaultdict(list)
    ids_unidade = {u.pk for u in unidades}
    ids_distrito = {d.pk for d in distritos}
    for atribuicao in atribuidos:
        destino = por_unidade if atribuicao.unidade_id else por_distrito
        local_id = atribuicao.unidade_id or atribuicao.distrito_id
        if local_id not in (ids_unidade if atribuicao.unidade_id else ids_distrito):
            continue
        destino[local_id].append({
            "id": atribuicao.pessoa_id,
            "nome": atribuicao.pessoa.nome,
            "categoria": atribuicao.categoria.codigo,
            "categoria_nome": atribuicao.categoria.nome,
            "categoria_id": atribuicao.categoria_id,
        })
    escopos = []
    for unidade in unidades:
        registros = {r.indicador_id: r for r in RegistroIndicador.objects.filter(
            competencia=competencia, unidade=unidade, categoria=unidade.tipo.categoria,
        )}
        tarefas = _tarefas_do_escopo(
            competencia, unidade=unidade, categoria=unidade.tipo.categoria,
            filhos=filhos, pesos=pesos, regras=regras, registros=registros, usuario=usuario,
        )
        escopos.append({
            "tipo": "UNIDADE", "id": unidade.pk, "nome": unidade.nome,
            "codigo": unidade.codigo, "distrito": unidade.distrito.pk,
            "distrito_nome": unidade.distrito.nome,
            "categoria": unidade.tipo.categoria_id, "categoria_codigo": unidade.tipo.categoria.codigo,
            "responsaveis": por_unidade.get(unidade.pk, []),
            "tarefas": tarefas,
        })
    # A fonte técnica distrital I5 só é necessária se pelo menos uma pessoa
    # avaliada ativa, com vínculo vigente neste mês, possuir peso > 0 em I5.
    # O cadastramento de vários avaliados não duplica o dado de origem.
    if categoria_base is not None:
        categorias_exigem_i5 = {
            categoria_id for categoria_id, indicadores_pesos in pesos.items()
            if any(raiz.codigo == "5" and peso > 0 for raiz, peso in indicadores_pesos)
        }
        for distrito in distritos:
            responsaveis = por_distrito.get(distrito.pk, [])
            tem_responsavel = bool(responsaveis)
            exige_i5 = any(
                responsavel["categoria_id"] in categorias_exigem_i5
                for responsavel in responsaveis
            )
            tarefas = []
            if exige_i5:
                registros = {r.indicador_id: r for r in RegistroIndicador.objects.filter(
                    competencia=competencia, distrito=distrito, categoria=categoria_base,
                )}
                tarefas = _tarefas_do_escopo(
                    competencia, distrito=distrito, categoria=categoria_base,
                    filhos=filhos, pesos=pesos, regras=regras, registros=registros,
                    usuario=usuario, distrito_origem=True,
                )
                # I1-I4 são resultados derivados das unidades; só I5 possui
                # folha de entrada distrital própria neste recorte da CAM 1.2.
                tarefas = [t for t in tarefas if t["codigo"] == "5"]
            if not tem_responsavel:
                estado_configuracao = "SEM_RESPONSAVEL"
                aviso = (
                    "Não há gestor distrital com responsabilidade vigente nesta competência. "
                    "Defina os avaliados no Configurador; nenhuma tarefa distrital será exigida até lá."
                )
            elif not exige_i5:
                estado_configuracao = "SEM_I5_APLICAVEL"
                aviso = (
                    "As categorias distritais vigentes não utilizam o Indicador 5. "
                    "Não há lançamento distrital de I5 nesta competência."
                )
            else:
                estado_configuracao = "CONFIGURADO"
                aviso = (
                    "Origem técnica única do I5; o mesmo dado será reutilizado nas "
                    "avaliações das categorias elegíveis. I1–I4 pertencem à Apuração."
                )
            escopos.append({
                "tipo": "DISTRITO", "id": distrito.pk, "nome": distrito.nome,
                "codigo": distrito.codigo, "categoria": categoria_base.pk,
                "categoria_codigo": categoria_base.codigo,
                "responsaveis": responsaveis,
                "estado_configuracao": estado_configuracao,
                "aviso": aviso, "tarefas": tarefas,
            })
    return {"competencia": competencia.pk, "mes": competencia.mes.isoformat(),
            "versao": competencia.versao.codigo, "estado": competencia.estado,
            "escopos": escopos}


def localizar_tarefa(tarefas, *, unidade_id=None, distrito_id=None, indicador_id=None):
    for escopo in tarefas["escopos"]:
        if unidade_id is not None and (escopo["tipo"] != "UNIDADE" or escopo["id"] != unidade_id):
            continue
        if distrito_id is not None and (escopo["tipo"] != "DISTRITO" or escopo["id"] != distrito_id):
            continue
        for tarefa in escopo["tarefas"]:
            if tarefa["indicador"] == indicador_id:
                return tarefa
    return None
