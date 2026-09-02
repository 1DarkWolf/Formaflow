from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum

from apps.core.models import ModeloTemporal
from apps.organizacoes.models import EntidadeFormadora


class AcaoFormacao(ModeloTemporal):
    class Tipologia(models.TextChoices):
        POR_DEFINIR = "", "Por definir"
        CNQ = "CNQ", "CNQ"
        EXTRA_CNQ = "EXTRA_CNQ", "Extra-CNQ"
        MISTA = "MISTA", "Mista"

    class Estado(models.TextChoices):
        PLANEADA = "PLANEADA", "Planeada"
        EM_CURSO = "EM_CURSO", "Em curso"
        CONCLUIDA_COM_APROVEITAMENTO = (
            "CONCLUIDA_COM_APROVEITAMENTO",
            "Concluída com aproveitamento",
        )
        CONCLUIDA_SEM_APROVEITAMENTO = (
            "CONCLUIDA_SEM_APROVEITAMENTO",
            "Concluída sem aproveitamento",
        )
        INTERROMPIDA = "INTERROMPIDA", "Interrompida"
        CANCELADA = "CANCELADA", "Cancelada"

    entidade_formadora = models.ForeignKey(
        EntidadeFormadora,
        on_delete=models.PROTECT,
        related_name="acoes_formacao",
    )
    referencia_externa = models.CharField(max_length=100, blank=True)
    designacao = models.CharField("designação", max_length=255)
    area_codigo = models.CharField("código da área", max_length=20, blank=True)
    area_designacao = models.CharField("designação da área", max_length=255, blank=True)
    modalidade = models.CharField(max_length=120, blank=True)
    tipologia = models.CharField(
        max_length=10,
        choices=Tipologia.choices,
        blank=True,
        default=Tipologia.POR_DEFINIR,
        editable=False,
    )
    inicio_previsto = models.DateField("início previsto")
    fim_previsto = models.DateField("fim previsto")
    inicio_real = models.DateField("início real", blank=True, null=True)
    fim_real = models.DateField("fim real", blank=True, null=True)
    local = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=40, choices=Estado.choices, default=Estado.PLANEADA)
    horas_totais = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
    )

    class Meta:
        verbose_name = "ação de formação"
        verbose_name_plural = "ações de formação"
        ordering = ("-inicio_previsto", "designacao")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fim_previsto__gte=models.F("inicio_previsto")),
                name="formacoes_acao_periodo_previsto_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(horas_totais__gte=0),
                name="formacoes_acao_horas_nao_negativas",
            ),
        ]

    def __str__(self):
        return self.designacao

    def clean(self):
        super().clean()
        errors = {}
        if self.fim_previsto and self.inicio_previsto:
            if self.fim_previsto < self.inicio_previsto:
                errors["fim_previsto"] = "O fim previsto não pode ser anterior ao início."
            if self.fim_previsto.year - self.inicio_previsto.year > 2:
                errors["fim_previsto"] = "A ação não pode abranger mais de três anos civis."
        if self.inicio_real and self.fim_real and self.fim_real < self.inicio_real:
            errors["fim_real"] = "O fim real não pode ser anterior ao início real."
        if self.estado == self.Estado.EM_CURSO and not self.inicio_real:
            errors["inicio_real"] = "Indique o início real para colocar a ação em curso."
        if (
            self.estado
            in {
                self.Estado.CONCLUIDA_COM_APROVEITAMENTO,
                self.Estado.CONCLUIDA_SEM_APROVEITAMENTO,
            }
            and not self.fim_real
        ):
            errors["fim_real"] = "Indique o fim real para concluir a ação."
        if errors:
            raise ValidationError(errors)

    def recalcular_resumos(self):
        componentes = self.componentes.all()
        tipos = set(componentes.values_list("tipo", flat=True))
        if tipos == {ComponenteFormacao.Tipo.CNQ}:
            tipologia = self.Tipologia.CNQ
        elif tipos == {ComponenteFormacao.Tipo.EXTRA_CNQ}:
            tipologia = self.Tipologia.EXTRA_CNQ
        elif tipos:
            tipologia = self.Tipologia.MISTA
        else:
            tipologia = self.Tipologia.POR_DEFINIR
        total = componentes.aggregate(total=Sum("horas"))["total"] or Decimal("0")
        self.__class__.objects.filter(pk=self.pk).update(
            tipologia=tipologia,
            horas_totais=total,
        )
        self.tipologia = tipologia
        self.horas_totais = total


class ComponenteFormacao(ModeloTemporal):
    class Tipo(models.TextChoices):
        CNQ = "CNQ", "CNQ"
        EXTRA_CNQ = "EXTRA_CNQ", "Extra-CNQ"

    acao_formacao = models.ForeignKey(
        AcaoFormacao,
        on_delete=models.CASCADE,
        related_name="componentes",
    )
    ordem = models.PositiveSmallIntegerField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    codigo_cnq = models.CharField("código CNQ", max_length=30, blank=True)
    designacao = models.CharField("designação", max_length=255)
    area_codigo = models.CharField("código da área", max_length=20, blank=True)
    referencial = models.CharField(max_length=255, blank=True)
    horas = models.DecimalField(max_digits=8, decimal_places=2)
    justificacao_extra_cnq = models.TextField("justificação extra-CNQ", blank=True)

    class Meta:
        verbose_name = "componente de formação"
        verbose_name_plural = "componentes de formação"
        ordering = ("acao_formacao", "ordem")
        constraints = [
            models.UniqueConstraint(
                fields=("acao_formacao", "ordem"),
                name="formacoes_componente_ordem_unica",
            ),
            models.CheckConstraint(
                condition=models.Q(ordem__gt=0),
                name="formacoes_componente_ordem_positiva",
            ),
            models.CheckConstraint(
                condition=models.Q(horas__gt=0),
                name="formacoes_componente_horas_positivas",
            ),
        ]

    def __str__(self):
        return f"{self.ordem}. {self.designacao}"

    def clean(self):
        super().clean()
        errors = {}
        if self.horas is not None and self.horas <= 0:
            errors["horas"] = "A carga horária deve ser superior a zero."
        if self.tipo == self.Tipo.CNQ and not self.codigo_cnq.strip():
            errors["codigo_cnq"] = "O código CNQ é obrigatório nesta componente."
        if self.tipo == self.Tipo.EXTRA_CNQ:
            if self.codigo_cnq.strip():
                errors["codigo_cnq"] = "Uma componente extra-CNQ não pode ter código CNQ."
            if not self.justificacao_extra_cnq.strip():
                errors["justificacao_extra_cnq"] = (
                    "Justifique a relevância da componente extra-CNQ."
                )
        if (
            self.area_codigo
            and self.acao_formacao_id
            and self.acao_formacao.area_codigo
            and self.area_codigo != self.acao_formacao.area_codigo
        ):
            errors["area_codigo"] = "A área deve coincidir com a área da ação."
        if errors:
            raise ValidationError(errors)

    @transaction.atomic
    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        self.acao_formacao.recalcular_resumos()
        return result

    @transaction.atomic
    def delete(self, *args, **kwargs):
        action = self.acao_formacao
        result = super().delete(*args, **kwargs)
        action.recalcular_resumos()
        return result
