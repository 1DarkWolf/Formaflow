from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from .managers import GestorUtilizadores
from .validators import normalizar_nif, validar_data_nao_futura, validar_nif

codigo_pais_validator = RegexValidator(
    regex=r"^[A-Z]{2}$",
    message="Introduza um código de país ISO com duas letras maiúsculas.",
)


class Utilizador(AbstractBaseUser, PermissionsMixin):
    """Authentication identity shared by every Forma Flow role."""

    email = models.EmailField("email", max_length=254, unique=True)
    nome_proprio = models.CharField("nome próprio", max_length=150)
    apelido = models.CharField(max_length=150)
    is_active = models.BooleanField("ativo", db_column="ativo", default=True)
    equipa_interna = models.BooleanField(
        default=False,
        help_text="Indica uma conta operacional interna do Forma Flow.",
    )
    is_staff = models.BooleanField(
        "acesso à administração técnica",
        default=False,
        help_text="Permite entrar na administração técnica do Django.",
    )
    last_login = models.DateTimeField(
        "último acesso",
        blank=True,
        null=True,
        db_column="ultimo_acesso_em",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = GestorUtilizadores()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome_proprio", "apelido"]

    class Meta:
        verbose_name = "utilizador"
        verbose_name_plural = "utilizadores"
        ordering = ("email",)
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="contas_utilizador_email_ci_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.__class__.objects.normalizar_email(self.email)

    def save(self, *args, **kwargs):
        self.email = self.__class__.objects.normalizar_email(self.email)
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.nome_proprio} {self.apelido}".strip()

    def get_short_name(self):
        return self.nome_proprio

    def __str__(self):
        return self.email


class PerfilCandidato(models.Model):
    """Current personal data for a user who can participate in applications."""

    utilizador = models.OneToOneField(
        Utilizador,
        on_delete=models.PROTECT,
        related_name="perfil_candidato",
    )
    nif = models.CharField(max_length=9, unique=True, validators=[validar_nif])
    data_nascimento = models.DateField(
        "data de nascimento",
        validators=[validar_data_nao_futura],
    )
    telefone = models.CharField(max_length=30, blank=True)
    nacionalidade = models.CharField(
        max_length=2,
        blank=True,
        validators=[codigo_pais_validator],
    )
    morada = models.CharField(max_length=255, blank=True)
    codigo_postal = models.CharField("código postal", max_length=20, blank=True)
    localidade = models.CharField(max_length=120, blank=True)
    pais = models.CharField(
        "país",
        max_length=2,
        blank=True,
        validators=[codigo_pais_validator],
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil de candidato"
        verbose_name_plural = "perfis de candidato"
        ordering = ("utilizador__nome_proprio", "utilizador__apelido")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nif__regex=r"^\d{9}$"),
                name="contas_perfil_nif_nove_digitos",
            ),
        ]

    def __str__(self):
        return self.utilizador.get_full_name() or self.utilizador.email

    def save(self, *args, **kwargs):
        self._normalizar_campos()
        return super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        self._normalizar_campos()
        return super().full_clean(*args, **kwargs)

    def _normalizar_campos(self):
        self.nif = normalizar_nif(self.nif)
        self.nacionalidade = self.nacionalidade.strip().upper()
        self.pais = self.pais.strip().upper()
        self.telefone = self.telefone.strip()


class TentativaAutenticacao(models.Model):
    """Aggregated failed logins keyed by a non-reversible identifier and address."""

    chave = models.CharField(max_length=64, unique=True, editable=False)
    falhas = models.PositiveSmallIntegerField(default=0, editable=False)
    janela_iniciada_em = models.DateTimeField(editable=False)
    bloqueado_ate = models.DateTimeField(blank=True, null=True, editable=False)
    atualizado_em = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "tentativa de autenticação"
        verbose_name_plural = "tentativas de autenticação"
        indexes = [
            models.Index(fields=("bloqueado_ate",), name="contas_login_bloqueio_idx"),
        ]

    def __str__(self):
        return f"Tentativas {self.chave[:8]}… ({self.falhas})"
