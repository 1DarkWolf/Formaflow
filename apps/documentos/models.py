import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q

from apps.candidaturas.models import (
    BeneficiarioCandidatura,
    Candidatura,
    ParticipacaoFormacao,
)
from apps.core.models import ModeloTemporal
from apps.regras.models import TipoDocumento


class FaseDocumento(models.TextChoices):
    PREPARACAO = "PREPARACAO", "Preparação"
    ANALISE = "ANALISE", "Análise"
    ACEITACAO = "ACEITACAO", "Aceitação"
    ACOMPANHAMENTO = "ACOMPANHAMENTO", "Acompanhamento"
    ENCERRAMENTO = "ENCERRAMENTO", "Encerramento"
    FINANCEIRA = "FINANCEIRA", "Financeira"


class EstadoDocumento(models.TextChoices):
    EM_FALTA = "EM_FALTA", "Em falta"
    RECEBIDO = "RECEBIDO", "Recebido"
    EM_VALIDACAO = "EM_VALIDACAO", "Em validação"
    VALIDO = "VALIDO", "Válido"
    INVALIDO = "INVALIDO", "Inválido"
    DISPENSADO = "DISPENSADO", "Dispensado com justificação"


class FicheiroArmazenado(models.Model):
    class EstadoUpload(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        FALHOU = "FALHOU", "Falhou"
        REMOVIDO = "REMOVIDO", "Removido"

    class EstadoSeguranca(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        SEGURO = "SEGURO", "Seguro"
        SUSPEITO = "SUSPEITO", "Suspeito"
        BLOQUEADO = "BLOQUEADO", "Bloqueado"

    chave_armazenamento = models.CharField(max_length=500, unique=True, editable=False)
    nome_original = models.CharField(max_length=255, editable=False)
    tipo_mime = models.CharField(max_length=100, editable=False)
    tamanho_bytes = models.PositiveBigIntegerField(editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    estado_upload = models.CharField(
        max_length=10,
        choices=EstadoUpload.choices,
        default=EstadoUpload.PENDENTE,
        editable=False,
    )
    estado_seguranca = models.CharField(
        max_length=10,
        choices=EstadoSeguranca.choices,
        default=EstadoSeguranca.PENDENTE,
        editable=False,
    )
    carregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ficheiros_carregados",
        editable=False,
    )
    carregado_em = models.DateTimeField(auto_now_add=True, editable=False)
    removido_em = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        verbose_name = "ficheiro armazenado"
        verbose_name_plural = "ficheiros armazenados"
        ordering = ("-carregado_em",)
        constraints = [
            models.CheckConstraint(
                condition=Q(tamanho_bytes__gte=0),
                name="documentos_ficheiro_tamanho_nao_negativo",
            ),
        ]

    def __str__(self):
        return self.nome_original


class RequisitoDocumento(ModeloTemporal):
    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.CASCADE,
        related_name="requisitos_documentais",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.CASCADE,
        related_name="requisitos_documentais",
        blank=True,
        null=True,
    )
    participacao = models.ForeignKey(
        ParticipacaoFormacao,
        on_delete=models.CASCADE,
        related_name="requisitos_documentais",
        blank=True,
        null=True,
    )
    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name="requisitos",
    )
    fase = models.CharField(max_length=16, choices=FaseDocumento.choices)
    codigo_regra = models.CharField("código da regra", max_length=40, blank=True)
    obrigatorio = models.BooleanField(default=True)
    bloqueante = models.BooleanField(default=True)
    data_limite = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(
        max_length=12,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.EM_FALTA,
        editable=False,
    )
    dispensado_em = models.DateTimeField(blank=True, null=True, editable=False)
    dispensado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requisitos_documentais_dispensados",
        blank=True,
        null=True,
        editable=False,
    )
    motivo_dispensa = models.TextField(blank=True, editable=False)

    class Meta:
        verbose_name = "requisito documental"
        verbose_name_plural = "requisitos documentais"
        ordering = ("fase", "beneficiario", "participacao", "tipo_documento")
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "tipo_documento", "fase"),
                condition=Q(beneficiario__isnull=True, participacao__isnull=True),
                name="documentos_requisito_global_unico",
            ),
            models.UniqueConstraint(
                fields=("beneficiario", "tipo_documento", "fase"),
                condition=Q(beneficiario__isnull=False, participacao__isnull=True),
                name="documentos_requisito_benef_unico",
            ),
            models.UniqueConstraint(
                fields=("participacao", "tipo_documento", "fase"),
                condition=Q(participacao__isnull=False),
                name="documentos_requisito_part_unico",
            ),
        ]

    def __str__(self):
        return f"{self.tipo_documento} — {self.get_estado_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if self.participacao_id:
            if self.participacao.beneficiario.candidatura_id != self.candidatura_id:
                errors["participacao"] = "A participação não pertence à candidatura."
            if self.beneficiario_id != self.participacao.beneficiario_id:
                errors["beneficiario"] = "A participação deve corresponder ao beneficiário."
        if self.estado == EstadoDocumento.DISPENSADO:
            if not self.motivo_dispensa.strip():
                errors["motivo_dispensa"] = "A dispensa exige uma justificação."
            if not self.dispensado_em or not self.dispensado_por_id:
                errors["estado"] = "A dispensa exige autor e data."
        if errors:
            raise ValidationError(errors)


class Documento(ModeloTemporal):
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.CASCADE,
        related_name="documentos",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.CASCADE,
        related_name="documentos",
        blank=True,
        null=True,
    )
    participacao = models.ForeignKey(
        ParticipacaoFormacao,
        on_delete=models.CASCADE,
        related_name="documentos",
        blank=True,
        null=True,
    )
    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name="documentos",
    )
    requisito = models.ForeignKey(
        RequisitoDocumento,
        on_delete=models.PROTECT,
        related_name="documentos",
        blank=True,
        null=True,
    )
    fase = models.CharField(max_length=16, choices=FaseDocumento.choices)
    titulo = models.CharField("título", max_length=255, blank=True)
    estado_atual = models.CharField(
        max_length=12,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.RECEBIDO,
        editable=False,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documentos_criados",
        editable=False,
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ("candidatura", "fase", "tipo_documento")
        constraints = [
            models.UniqueConstraint(
                fields=("requisito",),
                condition=Q(requisito__isnull=False),
                name="documentos_documento_por_requisito_unico",
            ),
        ]

    def __str__(self):
        return self.titulo or str(self.tipo_documento)

    def clean(self):
        super().clean()
        errors = {}
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if self.participacao_id:
            if self.participacao.beneficiario.candidatura_id != self.candidatura_id:
                errors["participacao"] = "A participação não pertence à candidatura."
            if self.beneficiario_id != self.participacao.beneficiario_id:
                errors["beneficiario"] = "A participação deve corresponder ao beneficiário."
        if self.requisito_id:
            requirement = self.requisito
            if requirement.candidatura_id != self.candidatura_id:
                errors["requisito"] = "O requisito não pertence à candidatura."
            if requirement.tipo_documento_id != self.tipo_documento_id:
                errors["tipo_documento"] = "O tipo não corresponde ao requisito."
            if requirement.beneficiario_id != self.beneficiario_id:
                errors["beneficiario"] = "O âmbito não corresponde ao requisito."
            if requirement.participacao_id != self.participacao_id:
                errors["participacao"] = "O âmbito não corresponde ao requisito."
            if requirement.fase != self.fase:
                errors["fase"] = "A fase não corresponde ao requisito."
        if errors:
            raise ValidationError(errors)


class VersaoDocumento(models.Model):
    class EstadoValidacao(models.TextChoices):
        RECEBIDO = "RECEBIDO", "Recebido"
        EM_VALIDACAO = "EM_VALIDACAO", "Em validação"
        VALIDO = "VALIDO", "Válido"
        INVALIDO = "INVALIDO", "Inválido"
        SUBSTITUIDO = "SUBSTITUIDO", "Substituído"

    documento = models.ForeignKey(
        Documento,
        on_delete=models.PROTECT,
        related_name="versoes",
    )
    numero = models.PositiveIntegerField(editable=False)
    ficheiro = models.OneToOneField(
        FicheiroArmazenado,
        on_delete=models.PROTECT,
        related_name="versao_documento",
    )
    estado_validacao = models.CharField(
        max_length=12,
        choices=EstadoValidacao.choices,
        default=EstadoValidacao.RECEBIDO,
        editable=False,
    )
    corrente = models.BooleanField(default=True, editable=False)
    emitido_em = models.DateField(blank=True, null=True)
    valido_ate = models.DateField(blank=True, null=True)
    carregada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="versoes_documentais_carregadas",
        editable=False,
    )
    carregada_em = models.DateTimeField(auto_now_add=True, editable=False)
    validada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="versoes_documentais_validadas",
        blank=True,
        null=True,
        editable=False,
    )
    validada_em = models.DateTimeField(blank=True, null=True, editable=False)
    observacao_validacao = models.TextField("observação da validação", blank=True, editable=False)
    motivo_substituicao = models.TextField("motivo da substituição", blank=True, editable=False)

    class Meta:
        verbose_name = "versão de documento"
        verbose_name_plural = "versões de documentos"
        ordering = ("documento", "-numero")
        constraints = [
            models.UniqueConstraint(
                fields=("documento", "numero"),
                name="documentos_versao_numero_unico",
            ),
            models.UniqueConstraint(
                fields=("documento",),
                condition=Q(corrente=True),
                name="documentos_versao_corrente_unica",
            ),
            models.CheckConstraint(
                condition=Q(numero__gt=0),
                name="documentos_versao_numero_positivo",
            ),
            models.CheckConstraint(
                condition=Q(valido_ate__isnull=True)
                | Q(emitido_em__isnull=True)
                | Q(valido_ate__gte=models.F("emitido_em")),
                name="documentos_versao_validade_coerente",
            ),
        ]

    def __str__(self):
        return f"{self.documento} — v{self.numero}"

    def save(self, *args, **kwargs):
        if self.pk and self.__class__.objects.filter(pk=self.pk).exists():
            raise ValidationError("Uma versão documental é imutável; crie uma nova versão.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Uma versão documental não pode ser eliminada.")

    def clean(self):
        super().clean()
        if self.valido_ate and self.emitido_em and self.valido_ate < self.emitido_em:
            raise ValidationError({"valido_ate": "A validade não pode anteceder a emissão."})
        if (
            self.estado_validacao == self.EstadoValidacao.INVALIDO
            and not self.observacao_validacao.strip()
        ):
            raise ValidationError(
                {"observacao_validacao": "Explique por que motivo o documento é inválido."}
            )


class SnapshotSubmissao(models.Model):
    class Finalidade(models.TextChoices):
        SUBMISSAO = "SUBMISSAO", "Submissão"
        TERMO = "TERMO", "Termo"
        ENCERRAMENTO = "ENCERRAMENTO", "Encerramento"
        CORRECAO = "CORRECAO", "Correção"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="snapshots_submissao",
    )
    transicao = models.ForeignKey(
        "workflow.TransicaoCandidatura",
        on_delete=models.PROTECT,
        related_name="snapshots_submissao",
        blank=True,
        null=True,
    )
    finalidade = models.CharField(max_length=12, choices=Finalidade.choices)
    sequencia = models.PositiveIntegerField(editable=False)
    capturado_em = models.DateTimeField(auto_now_add=True, editable=False)
    capturado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="snapshots_capturados",
        editable=False,
    )
    dados = models.JSONField(encoder=DjangoJSONEncoder, editable=False)
    versao_esquema = models.PositiveIntegerField(default=1, editable=False)
    hash_conteudo = models.CharField(max_length=64, editable=False)
    versoes_documentos = models.ManyToManyField(
        VersaoDocumento,
        related_name="snapshots_submissao",
        blank=True,
    )

    class Meta:
        verbose_name = "snapshot de submissão"
        verbose_name_plural = "snapshots de submissão"
        ordering = ("candidatura", "finalidade", "-sequencia")
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "finalidade", "sequencia"),
                name="documentos_snapshot_sequencia_unica",
            ),
            models.CheckConstraint(
                condition=Q(sequencia__gt=0),
                name="documentos_snapshot_sequencia_positiva",
            ),
            models.CheckConstraint(
                condition=Q(versao_esquema__gt=0),
                name="documentos_snapshot_esquema_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.candidatura} — {self.get_finalidade_display()} {self.sequencia}"

    def save(self, *args, **kwargs):
        if self.pk and self.__class__.objects.filter(pk=self.pk).exists():
            raise ValidationError("Um snapshot é imutável; crie uma nova fotografia.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Um snapshot não pode ser eliminado.")
