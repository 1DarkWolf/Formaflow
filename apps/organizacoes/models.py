import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.contas.models import PerfilCandidato
from apps.core.models import ModeloTemporal

from .security import calcular_hash_iban, cifrar_iban, validar_iban
from .validators import normalizar_nipc, validar_nipc


class Empresa(ModeloTemporal):
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nipc = models.CharField(max_length=9, unique=True, validators=[validar_nipc])
    denominacao_legal = models.CharField("denominação legal", max_length=255)
    nome_comercial = models.CharField(max_length=255, blank=True)
    natureza_juridica = models.CharField("natureza jurídica", max_length=120, blank=True)
    cae_principal = models.CharField("CAE principal", max_length=10, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    morada = models.CharField(max_length=255, blank=True)
    codigo_postal = models.CharField("código postal", max_length=20, blank=True)
    localidade = models.CharField(max_length=120, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        ordering = ("denominacao_legal",)

    def __str__(self):
        return self.nome_comercial or self.denominacao_legal

    def save(self, *args, **kwargs):
        self.nipc = normalizar_nipc(self.nipc)
        return super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        self.nipc = normalizar_nipc(self.nipc)
        return super().full_clean(*args, **kwargs)


class AssociacaoEmpresaQuerySet(models.QuerySet):
    def vigentes(self, no_momento):
        return self.filter(ativa=True, inicio_em__lte=no_momento).filter(
            Q(fim_em__isnull=True) | Q(fim_em__gte=no_momento)
        )


class AssociacaoEmpresa(ModeloTemporal):
    class Papel(models.TextChoices):
        GESTOR = "GESTOR", "Gestor"
        RECURSOS_HUMANOS = "RECURSOS_HUMANOS", "Recursos humanos"
        CONSULTA = "CONSULTA", "Consulta"

    utilizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="associacoes_empresa",
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="associacoes",
    )
    papel = models.CharField(max_length=20, choices=Papel.choices)
    ativa = models.BooleanField(default=True)
    inicio_em = models.DateTimeField()
    fim_em = models.DateTimeField(blank=True, null=True)
    concedida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="associacoes_empresa_concedidas",
    )

    objects = AssociacaoEmpresaQuerySet.as_manager()

    class Meta:
        verbose_name = "associação a empresa"
        verbose_name_plural = "associações a empresas"
        ordering = ("empresa", "utilizador", "papel")
        constraints = [
            models.UniqueConstraint(
                fields=("utilizador", "empresa", "papel"),
                condition=Q(ativa=True),
                name="organizacoes_associacao_ativa_unica",
            ),
            models.CheckConstraint(
                condition=Q(fim_em__isnull=True) | Q(fim_em__gte=models.F("inicio_em")),
                name="organizacoes_associacao_periodo_valido",
            ),
        ]

    def __str__(self):
        return f"{self.utilizador} — {self.empresa} ({self.get_papel_display()})"

    def clean(self):
        super().clean()
        if self.fim_em and self.fim_em < self.inicio_em:
            raise ValidationError({"fim_em": "A data final não pode ser anterior à inicial."})


class VinculoLaboral(ModeloTemporal):
    class Situacao(models.TextChoices):
        CONTA_OUTREM = "CONTA_OUTREM", "Trabalhador por conta de outrem"
        CONTA_PROPRIA = "CONTA_PROPRIA", "Trabalhador por conta própria"
        DESEMPREGADO = "DESEMPREGADO", "Desempregado"

    candidato = models.ForeignKey(
        PerfilCandidato,
        on_delete=models.PROTECT,
        related_name="vinculos_laborais",
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="vinculos_laborais",
        blank=True,
        null=True,
    )
    situacao = models.CharField("situação", max_length=20, choices=Situacao.choices)
    inicio_em = models.DateField()
    fim_em = models.DateField(blank=True, null=True)
    inscricao_iefp_em = models.DateField("inscrição no IEFP", blank=True, null=True)
    nivel_qualificacao = models.PositiveSmallIntegerField(
        "nível de qualificação",
        blank=True,
        null=True,
    )
    confirmado_em = models.DateTimeField(blank=True, null=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="vinculos_laborais_confirmados",
    )

    class Meta:
        verbose_name = "vínculo laboral"
        verbose_name_plural = "vínculos laborais"
        ordering = ("-inicio_em",)
        constraints = [
            models.CheckConstraint(
                condition=Q(fim_em__isnull=True) | Q(fim_em__gte=models.F("inicio_em")),
                name="organizacoes_vinculo_periodo_valido",
            ),
            models.CheckConstraint(
                condition=(~Q(situacao="CONTA_OUTREM") | Q(empresa__isnull=False))
                & (~Q(situacao="DESEMPREGADO") | Q(empresa__isnull=True)),
                name="organizacoes_vinculo_empresa_coerente",
            ),
        ]

    def __str__(self):
        return f"{self.candidato} — {self.get_situacao_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.fim_em and self.fim_em < self.inicio_em:
            errors["fim_em"] = "A data final não pode ser anterior à inicial."
        if self.situacao == self.Situacao.CONTA_OUTREM and not self.empresa_id:
            errors["empresa"] = "A empresa é obrigatória neste tipo de vínculo."
        if self.situacao == self.Situacao.DESEMPREGADO and self.empresa_id:
            errors["empresa"] = "Uma situação de desemprego não pode indicar empresa."
        if errors:
            raise ValidationError(errors)


class ContaPagamento(ModeloTemporal):
    candidato = models.ForeignKey(
        PerfilCandidato,
        on_delete=models.PROTECT,
        related_name="contas_pagamento",
        blank=True,
        null=True,
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="contas_pagamento",
        blank=True,
        null=True,
    )
    iban_cifrado = models.TextField(editable=False)
    iban_hash = models.CharField(max_length=64, editable=False, db_index=True)
    iban_ultimos_4 = models.CharField(max_length=4, editable=False)
    nome_titular = models.CharField(max_length=255)
    principal = models.BooleanField(default=False)
    ativa = models.BooleanField(default=True)
    validada_em = models.DateTimeField(blank=True, null=True)
    validada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="contas_pagamento_validadas",
    )

    class Meta:
        verbose_name = "conta de pagamento"
        verbose_name_plural = "contas de pagamento"
        ordering = ("nome_titular",)
        constraints = [
            models.CheckConstraint(
                condition=(Q(candidato__isnull=False, empresa__isnull=True))
                | (Q(candidato__isnull=True, empresa__isnull=False)),
                name="organizacoes_conta_um_proprietario",
            ),
            models.UniqueConstraint(
                fields=("candidato",),
                condition=Q(principal=True, ativa=True),
                name="organizacoes_conta_principal_candidato_unica",
            ),
            models.UniqueConstraint(
                fields=("empresa",),
                condition=Q(principal=True, ativa=True),
                name="organizacoes_conta_principal_empresa_unica",
            ),
        ]

    def __str__(self):
        return f"{self.nome_titular} — {self.iban_mascarado}"

    @property
    def iban_mascarado(self):
        return f"•••• {self.iban_ultimos_4}"

    def definir_iban(self, iban):
        normalized = validar_iban(iban)
        self.iban_cifrado = cifrar_iban(normalized)
        self.iban_hash = calcular_hash_iban(normalized)
        self.iban_ultimos_4 = normalized[-4:]

    def clean(self):
        super().clean()
        if (self.candidato_id is None) == (self.empresa_id is None):
            raise ValidationError("A conta deve pertencer a um candidato ou a uma empresa.")
        if self.iban_ultimos_4 and len(self.iban_ultimos_4) != 4:
            raise ValidationError({"iban_ultimos_4": "O resumo do IBAN é inválido."})


class EntidadeFormadora(ModeloTemporal):
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nipc = models.CharField(max_length=9, unique=True, validators=[validar_nipc])
    denominacao_legal = models.CharField("denominação legal", max_length=255)
    nome_comercial = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    morada = models.CharField(max_length=255, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "entidade formadora"
        verbose_name_plural = "entidades formadoras"
        ordering = ("denominacao_legal",)

    def __str__(self):
        return self.nome_comercial or self.denominacao_legal

    def save(self, *args, **kwargs):
        self.nipc = normalizar_nipc(self.nipc)
        return super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        self.nipc = normalizar_nipc(self.nipc)
        return super().full_clean(*args, **kwargs)


class CertificacaoFormadora(ModeloTemporal):
    class Enquadramento(models.TextChoices):
        CERTIFICADA_DGERT = "CERTIFICADA_DGERT", "Certificada pela DGERT"
        DISPENSADA = "DISPENSADA", "Dispensada de certificação"
        PENDENTE_CONFIRMACAO = "PENDENTE_CONFIRMACAO", "Pendente de confirmação"

    entidade_formadora = models.ForeignKey(
        EntidadeFormadora,
        on_delete=models.PROTECT,
        related_name="certificacoes",
    )
    enquadramento = models.CharField(max_length=24, choices=Enquadramento.choices)
    area_codigo = models.CharField("código da área", max_length=20, blank=True)
    area_designacao = models.CharField("designação da área", max_length=255, blank=True)
    numero_certificacao = models.CharField("número da certificação", max_length=100, blank=True)
    valida_desde = models.DateField(blank=True, null=True)
    valida_ate = models.DateField(blank=True, null=True)
    verificada_em = models.DateTimeField(blank=True, null=True)
    verificada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="certificacoes_formadoras_verificadas",
    )

    class Meta:
        verbose_name = "certificação de entidade formadora"
        verbose_name_plural = "certificações de entidades formadoras"
        ordering = ("entidade_formadora", "area_codigo", "-valida_desde")

    def __str__(self):
        return f"{self.entidade_formadora} — {self.get_enquadramento_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.valida_desde and self.valida_ate and self.valida_ate < self.valida_desde:
            errors["valida_ate"] = "A validade final não pode ser anterior à inicial."
        if self.enquadramento == self.Enquadramento.CERTIFICADA_DGERT and not self.area_codigo:
            errors["area_codigo"] = "A área é obrigatória para certificações DGERT."
        if errors:
            raise ValidationError(errors)
