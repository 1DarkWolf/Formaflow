from django.contrib.auth.base_user import BaseUserManager


class GestorUtilizadores(BaseUserManager):
    """Create users whose canonical identifier is a lowercase email."""

    @staticmethod
    def normalizar_email(email):
        if not email:
            raise ValueError("O email é obrigatório.")
        return email.strip().lower()

    def get_by_natural_key(self, username):
        return self.get(email__iexact=self.normalizar_email(username))

    def create_user(self, email, password=None, **extra_fields):
        email = self.normalizar_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("equipa_interna", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_active") is not True:
            raise ValueError("Um superutilizador tem de estar ativo.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Um superutilizador tem de pertencer à administração técnica.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Um superutilizador tem de ter privilégios globais.")

        return self.create_user(email, password, **extra_fields)
