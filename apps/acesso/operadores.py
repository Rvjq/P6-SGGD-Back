"""Provisionamento restrito de contas operacionais pelo Configurador."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .interface import usuario_tem_permissao

PAPEIS_PERMITIDOS = {"Registrador", "Consultador"}


def exigir_configurador(usuario):
    if not usuario_tem_permissao(usuario, "acesso.gerenciar_competencia"):
        raise PermissionDenied("Operação reservada ao Configurador.")


def conta_operacional(usuario):
    papeis = set(usuario.groups.values_list("name", flat=True))
    return (bool(papeis) and papeis <= PAPEIS_PERMITIDOS and not usuario.is_staff
            and not usuario.is_superuser)


def apresentar(usuario):
    return {"id": usuario.pk, "nome": usuario.get_full_name() or usuario.email,
            "email": usuario.email, "nome_proprio": usuario.first_name, "sobrenome": usuario.last_name,
            "cargo": usuario.cargo, "ativo": usuario.is_active,
            "papeis": list(usuario.groups.values_list("name", flat=True))}


class OperadoresView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        exigir_configurador(request.user)
        Usuario = get_user_model()
        usuarios = Usuario.objects.filter(groups__name__in=PAPEIS_PERMITIDOS, is_staff=False,
                                          is_superuser=False).distinct().order_by("email")
        return Response([apresentar(u) for u in usuarios if conta_operacional(u)])

    def post(self, request):
        exigir_configurador(request.user)
        dados = request.data
        papel = dados.get("papel")
        if papel not in PAPEIS_PERMITIDOS:
            raise serializers.ValidationError({"papel": "Escolha Registrador ou Consultador."})
        email = dados.get("email", "")
        senha = dados.get("senha", "")
        nome = dados.get("nome", "")
        sobrenome = dados.get("sobrenome", "")
        cargo = dados.get("cargo", "")
        if not isinstance(email, str) or not email.strip() or "@" not in email:
            raise serializers.ValidationError({"email": "Informe um e-mail válido."})
        if not isinstance(nome, str) or not nome.strip() or len(nome) > 150:
            raise serializers.ValidationError({"nome": "Informe o nome (até 150 caracteres)."})
        if not isinstance(sobrenome, str) or len(sobrenome.strip()) > 150:
            raise serializers.ValidationError({"sobrenome": "Sobrenome inválido (máximo 150 caracteres)."})
        if not isinstance(cargo, str) or len(cargo.strip()) > 120:
            raise serializers.ValidationError({"cargo": "Cargo inválido (máximo 120 caracteres)."})
        if not isinstance(senha, str):
            raise serializers.ValidationError({"senha": "Informe uma senha."})
        Usuario = get_user_model()
        usuario = Usuario(email=email.strip().lower(), username="", first_name=nome.strip(),
                          last_name=sobrenome.strip(), cargo=cargo.strip())
        try:
            validate_password(senha, user=usuario)
        except DjangoValidationError as erro:
            raise serializers.ValidationError({"senha": erro.messages}) from erro
        if Usuario.objects.filter(email__iexact=usuario.email).exists():
            raise serializers.ValidationError({"email": "Este e-mail já está cadastrado."})
        with transaction.atomic():
            # O username segue interno; não abre acesso a is_staff nem a privilégios administrativos.
            import uuid
            usuario.username = "sggd-" + uuid.uuid4().hex[:24]
            usuario.set_password(senha)
            try:
                usuario.save()
            except IntegrityError as erro:
                raise serializers.ValidationError({"email": "Não foi possível criar a conta: e-mail existente."}) from erro
            usuario.groups.add(Group.objects.get(name=papel))
        return Response(apresentar(usuario), status=201)


class OperadorDetalheView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, pk):
        exigir_configurador(request.user)
        Usuario = get_user_model()
        try:
            usuario = Usuario.objects.get(pk=pk)
        except Usuario.DoesNotExist:
            raise serializers.ValidationError("Conta operacional não encontrada.") from None
        if usuario.pk == request.user.pk or not conta_operacional(usuario):
            raise PermissionDenied("Esta conta não pode ser administrada pelo Configurador.")
        if set(request.data) != {"papel"} or request.data["papel"] not in PAPEIS_PERMITIDOS:
            raise serializers.ValidationError({"papel": "Apenas Registrador ou Consultador são permitidos."})
        usuario.groups.set([Group.objects.get(name=request.data["papel"])])
        return Response(apresentar(usuario))


class UsuariosConsultaView(APIView):
    """Consulta geral para o Configurador; não concede poderes de editar contas privilegiadas."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        exigir_configurador(request.user)
        Usuario = get_user_model()
        resultado = []
        for usuario in Usuario.objects.prefetch_related("groups").order_by("first_name", "email", "pk"):
            item = apresentar(usuario)
            item["administravel"] = conta_operacional(usuario)
            item["tipo_conta"] = "Administrador técnico" if usuario.is_superuser else (
                "Equipe técnica" if usuario.is_staff else "Conta SGGD")
            resultado.append(item)
        return Response(resultado)
