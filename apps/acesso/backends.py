from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Autentica usuários pelo e-mail, ignorando maiúsculas e minúsculas."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email")

        if not isinstance(email, str) or not email.strip() or not password:
            return None

        Usuario = get_user_model()

        try:
            usuario = Usuario.objects.get(email__iexact=email.strip())
        except Usuario.DoesNotExist:
            # Mantém o custo de hash mesmo quando o usuário não existe.
            Usuario().set_password(password)
            return None

        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario

        return None