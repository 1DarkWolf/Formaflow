from django.contrib.auth.tokens import PasswordResetTokenGenerator


class TokenAtivacaoConta(PasswordResetTokenGenerator):
    """Invalidate an activation link as soon as account state changes."""

    def _make_hash_value(self, user, timestamp):
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}"


token_ativacao_conta = TokenAtivacaoConta()
