from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.candidaturas.models import (
    BeneficiarioCandidatura,
    Candidatura,
    ParticipacaoFormacao,
)
from apps.core.models import ModeloTemporal
from apps.documentos.models import VersaoDocumento
from apps.regras.models import ConjuntoRegras
from apps.workflow.models import Prazo


class ApoioFinanceiro(ModeloTemporal):
    class Tipo(models.TextChoices):
        FORMACAO = "FORMACAO", "Formação"
        BOLSA = "BOLSA", "Bolsa de formação"
        REFEICAO = "REFEICAO", "Subsídio de refeição"
        TRANSPORTE = "TRANSPORTE", "Transporte coletivo"

    class Estado(models.TextChoices):
        SEM_APOIO = "SEM_APOIO", "Sem apoio"
        ESTIMADO = "ESTIMADO", "Estimado"
        APROVADO = "APROVADO", "Aprovado"
        PRIMEIRA_PRESTACAO_PENDENTE = (
            "PRIMEIRA_PRESTACAO_PENDENTE",
            "Primeira prestação pendente",
        )
        PARCIALMENTE_PAGO = "PARCIALMENTE_PAGO", "Parcialmente pago"
        PAGAMENTO_FINAL_PENDENTE = "PAGAMENTO_FINAL_PENDENTE", "Pagamento final pendente"
        PAGO = "PAGO", "Pago"
        RESTITUICAO_PENDENTE = "RESTITUICAO_PENDENTE", "Restituição pendente"
        RESTITUIDO = "RESTITUIDO", "Restituído"
        REGULARIZADO = "REGULARIZADO", "Regularizado"

    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.PROTECT,
        related_name="apoios_financeiros",
    )
    participacao = models.ForeignKey(
        ParticipacaoFormacao,
        on_delete=models.PROTECT,
        related_name="apoios_financeiros",
        blank=True,
        null=True,
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    custo_declarado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    financiamento_terceiros = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
    )
    valor_elegivel = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    valor_estimado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    valor_aprovado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    valor_final = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    moeda = models.CharField(max_length=3, default="EUR")
    estado = models.CharField(
        max_length=32,
        choices=Estado.choices,
        default=Estado.ESTIMADO,
        editable=False,
    )
    conjunto_regras = models.ForeignKey(
        ConjuntoRegras,
        on_delete=models.PROTECT,
        related_name="apoios_financeiros",
    )
    decomposicao_calculo = models.JSONField(default=dict, blank=True)
    calculado_em = models.DateTimeField(blank=True, null=True)
    calculado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="apoios_financeiros_calculados",
        blank=True,
        null=True,
    )
    confirmado_em = models.DateTimeField(blank=True, null=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="apoios_financeiros_confirmados",
        blank=True,
        null=True,
    )
    referencia_externa = models.CharField(max_length=100, blank=True)
    evidencia = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="apoios_financeiros_comprovados",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "apoio financeiro"
        verbose_name_plural = "apoios financeiros"
        ordering = ("beneficiario_id", "participacao_id", "tipo")
        indexes = [
            models.Index(fields=("estado", "tipo"), name="fin_apoio_estado_tipo_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("participacao", "tipo"),
                condition=Q(participacao__isnull=False),
                name="fin_apoio_participacao_tipo_unico",
            ),
            models.UniqueConstraint(
                fields=("beneficiario", "tipo"),
                condition=Q(participacao__isnull=True),
                name="fin_apoio_beneficiario_tipo_global_unico",
            ),
            models.CheckConstraint(
                condition=Q(financiamento_terceiros__gte=0),
                name="fin_apoio_terceiros_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(custo_declarado__isnull=True) | Q(custo_declarado__gte=0),
                name="fin_apoio_custo_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_elegivel__isnull=True) | Q(valor_elegivel__gte=0),
                name="fin_apoio_elegivel_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_estimado__isnull=True) | Q(valor_estimado__gte=0),
                name="fin_apoio_estimado_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_aprovado__isnull=True) | Q(valor_aprovado__gte=0),
                name="fin_apoio_aprovado_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(valor_final__isnull=True) | Q(valor_final__gte=0),
                name="fin_apoio_final_nao_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.beneficiario}"

    @property
    def candidatura(self):
        return self.beneficiario.candidatura

    def clean(self):
        super().clean()
        errors = {}
        if self.participacao_id and self.participacao.beneficiario_id != self.beneficiario_id:
            errors["participacao"] = "A participação não pertence ao beneficiário."
        for field in (
            "custo_declarado",
            "financiamento_terceiros",
            "valor_elegivel",
            "valor_estimado",
            "valor_aprovado",
            "valor_final",
        ):
            value = getattr(self, field)
            if value is not None and value < 0:
                errors[field] = "O valor não pode ser negativo."
        has_official_value = self.valor_aprovado is not None or self.valor_final is not None
        if has_official_value and (
            not self.confirmado_em
            or not self.confirmado_por_id
            or not (self.referencia_externa.strip() or self.evidencia_id)
        ):
            errors["valor_aprovado"] = (
                "Um valor oficial exige data, autor e referência ou evidência."
            )
        if self.evidencia_id and (
            self.evidencia.documento.candidatura_id != self.beneficiario.candidatura_id
        ):
            errors["evidencia"] = "A evidência não pertence à candidatura."
        if self.moeda != "EUR":
            errors["moeda"] = "O MVP suporta apenas valores em EUR."
        if errors:
            raise ValidationError(errors)


class MovimentoFinanceiro(ModeloTemporal):
    class Tipo(models.TextChoices):
        PRIMEIRA_PRESTACAO = "PRIMEIRA_PRESTACAO", "Primeira prestação"
        REMANESCENTE = "REMANESCENTE", "Remanescente"
        AJUSTE = "AJUSTE", "Ajuste"
        DEVOLUCAO = "DEVOLUCAO", "Devolução"

    class Direcao(models.TextChoices):
        CREDITO = "CREDITO", "Crédito"
        DEBITO = "DEBITO", "Débito"

    class Estado(models.TextChoices):
        PREVISTO = "PREVISTO", "Previsto"
        CONFIRMADO = "CONFIRMADO", "Confirmado"
        FALHOU = "FALHOU", "Falhou"
        CANCELADO = "CANCELADO", "Cancelado"
        REGULARIZADO = "REGULARIZADO", "Regularizado"

    apoio = models.ForeignKey(
        ApoioFinanceiro,
        on_delete=models.PROTECT,
        related_name="movimentos",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    direcao = models.CharField(max_length=8, choices=Direcao.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    previsto_para = models.DateTimeField(blank=True, null=True)
    efetivado_em = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=12, choices=Estado.choices)
    referencia_externa = models.CharField(max_length=100, blank=True)
    comprovativo = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="movimentos_financeiros_comprovados",
        blank=True,
        null=True,
    )
    registado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimentos_financeiros_registados",
    )
    chave_idempotencia = models.CharField(max_length=100)

    class Meta:
        verbose_name = "movimento financeiro"
        verbose_name_plural = "movimentos financeiros"
        ordering = ("apoio_id", "previsto_para", "pk")
        indexes = [
            models.Index(fields=("estado", "efetivado_em"), name="fin_mov_estado_data_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("apoio", "chave_idempotencia"),
                name="fin_mov_apoio_idempotencia_unica",
            ),
            models.CheckConstraint(condition=Q(valor__gt=0), name="fin_mov_valor_positivo"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.valor} {self.apoio.moeda}"

    @property
    def valor_assinado(self):
        return self.valor if self.direcao == self.Direcao.CREDITO else -self.valor

    def clean(self):
        super().clean()
        errors = {}
        self.chave_idempotencia = self.chave_idempotencia.strip()
        if self.valor is not None and self.valor <= 0:
            errors["valor"] = "O valor do movimento deve ser positivo."
        if not self.chave_idempotencia:
            errors["chave_idempotencia"] = "Indique uma chave de idempotência."
        if self.estado in {self.Estado.CONFIRMADO, self.Estado.REGULARIZADO} and (
            not self.efetivado_em or not (self.referencia_externa.strip() or self.comprovativo_id)
        ):
            errors["estado"] = "Um movimento efetivo exige data e referência ou comprovativo."
        if self.comprovativo_id and (
            self.comprovativo.documento.candidatura_id != self.apoio.beneficiario.candidatura_id
        ):
            errors["comprovativo"] = "O comprovativo não pertence à candidatura."
        if errors:
            raise ValidationError(errors)


class Restituicao(ModeloTemporal):
    class Estado(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PARCIAL = "PARCIAL", "Parcial"
        PAGA = "PAGA", "Paga"
        DISPENSADA = "DISPENSADA", "Dispensada"
        REGULARIZADA = "REGULARIZADA", "Regularizada"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="restituicoes",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.PROTECT,
        related_name="restituicoes",
        blank=True,
        null=True,
    )
    prazo = models.OneToOneField(
        Prazo,
        on_delete=models.PROTECT,
        related_name="restituicao",
    )
    notificada_em = models.DateTimeField()
    data_limite = models.DateTimeField()
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.TextField()
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.PENDENTE,
        editable=False,
    )
    valor_restituido = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    regularizada_em = models.DateTimeField(blank=True, null=True)
    referencia_externa = models.CharField(max_length=100, blank=True)
    evidencia = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="restituicoes_comprovadas",
        blank=True,
        null=True,
    )
    registada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="restituicoes_registadas",
    )
    chave_idempotencia = models.CharField(max_length=100)

    class Meta:
        verbose_name = "restituição"
        verbose_name_plural = "restituições"
        ordering = ("data_limite", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "chave_idempotencia"),
                name="fin_restituicao_idempotencia_unica",
            ),
            models.CheckConstraint(condition=Q(valor__gt=0), name="fin_rest_valor_positivo"),
            models.CheckConstraint(
                condition=Q(valor_restituido__gte=0),
                name="fin_rest_restituido_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(data_limite__gte=models.F("notificada_em")),
                name="fin_rest_limite_valido",
            ),
        ]

    def __str__(self):
        return f"Restituição — {self.valor} EUR"

    def clean(self):
        super().clean()
        errors = {}
        self.chave_idempotencia = self.chave_idempotencia.strip()
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if self.prazo_id and self.prazo.candidatura_id != self.candidatura_id:
            errors["prazo"] = "O prazo não pertence à candidatura."
        if self.valor is not None and self.valor <= 0:
            errors["valor"] = "O valor da restituição deve ser positivo."
        if self.valor_restituido is not None and self.valor_restituido < 0:
            errors["valor_restituido"] = "O valor restituído não pode ser negativo."
        if self.valor_restituido is not None and self.valor and self.valor_restituido > self.valor:
            errors["valor_restituido"] = "O valor restituído não pode exceder o notificado."
        if self.data_limite and self.notificada_em and self.data_limite < self.notificada_em:
            errors["data_limite"] = "O limite não pode anteceder a notificação."
        if not self.motivo.strip():
            errors["motivo"] = "Indique o motivo comunicado."
        if not self.chave_idempotencia:
            errors["chave_idempotencia"] = "Indique uma chave de idempotência."
        if not (self.referencia_externa.strip() or self.evidencia_id):
            errors["referencia_externa"] = "A restituição oficial exige referência ou evidência."
        if self.evidencia_id and self.evidencia.documento.candidatura_id != self.candidatura_id:
            errors["evidencia"] = "A evidência não pertence à candidatura."
        final_states = {self.Estado.PAGA, self.Estado.DISPENSADA, self.Estado.REGULARIZADA}
        if self.estado in final_states and not self.regularizada_em:
            errors["regularizada_em"] = "Um estado final exige data de regularização."
        if errors:
            raise ValidationError(errors)
