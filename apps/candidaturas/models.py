import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q

from apps.contas.models import PerfilCandidato
from apps.core.models import ModeloTemporal
from apps.formacoes.models import AcaoFormacao
from apps.organizacoes.models import ContaPagamento, Empresa, VinculoLaboral
from apps.regras.models import ConjuntoRegras


class Candidatura(ModeloTemporal):
    class Tipo(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        EMPRESARIAL = "EMPRESARIAL", "Empresarial"

    class Estado(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        PRONTA_SUBMISSAO = "PRONTA_SUBMISSAO", "Pronta para submissão"
        SUBMETIDA = "SUBMETIDA", "Submetida"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        AGUARDA_ELEMENTOS = "AGUARDA_ELEMENTOS", "Aguarda elementos adicionais"
        APROVADA_AGUARDA_TERMO = "APROVADA_AGUARDA_TERMO", "Aprovada — aguarda termo"
        APROVADA_ACOMPANHAMENTO = (
            "APROVADA_ACOMPANHAMENTO",
            "Aprovada — em acompanhamento",
        )
        ENCERRAMENTO_PREPARACAO = "ENCERRAMENTO_PREPARACAO", "Encerramento em preparação"
        ENCERRAMENTO_SUBMETIDO = "ENCERRAMENTO_SUBMETIDO", "Encerramento submetido"
        ENCERRAMENTO_ANALISE = "ENCERRAMENTO_ANALISE", "Encerramento em análise"
        ENCERRAMENTO_AGUARDA_ELEMENTOS = (
            "ENCERRAMENTO_AGUARDA_ELEMENTOS",
            "Encerramento aguarda elementos",
        )
        CONCLUIDA_AGUARDA_PAGAMENTO = (
            "CONCLUIDA_AGUARDA_PAGAMENTO",
            "Concluída — aguarda pagamento",
        )
        ENCERRADA = "ENCERRADA", "Encerrada"
        INDEFERIDA = "INDEFERIDA", "Indeferida"
        ARQUIVADA = "ARQUIVADA", "Arquivada pelo IEFP"
        DESISTIDA = "DESISTIDA", "Desistida"
        EXTINTA = "EXTINTA", "Extinta"
        REVOGADA = "REVOGADA", "Revogada"
        RASCUNHO_ARQUIVADO = "RASCUNHO_ARQUIVADO", "Rascunho arquivado"

    class ResultadoDecisao(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        DEFERIDA_TOTAL = "DEFERIDA_TOTAL", "Deferida totalmente"
        DEFERIDA_PARCIAL = "DEFERIDA_PARCIAL", "Deferida parcialmente"
        INDEFERIDA = "INDEFERIDA", "Indeferida"
        ARQUIVADA = "ARQUIVADA", "Arquivada"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    titular_candidato = models.ForeignKey(
        PerfilCandidato,
        on_delete=models.PROTECT,
        related_name="candidaturas_individuais",
        blank=True,
        null=True,
    )
    titular_empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="candidaturas_empresariais",
        blank=True,
        null=True,
    )
    conta_pagamento = models.ForeignKey(
        ContaPagamento,
        on_delete=models.PROTECT,
        related_name="candidaturas",
        blank=True,
        null=True,
    )
    conjunto_regras = models.ForeignKey(
        ConjuntoRegras,
        on_delete=models.PROTECT,
        related_name="candidaturas",
        blank=True,
        null=True,
    )
    estado_atual = models.CharField(
        max_length=40,
        choices=Estado.choices,
        default=Estado.RASCUNHO,
        editable=False,
    )
    resultado_decisao = models.CharField(
        max_length=20,
        choices=ResultadoDecisao.choices,
        default=ResultadoDecisao.PENDENTE,
        editable=False,
    )
    referencia_externa = models.CharField(max_length=100, blank=True, null=True, unique=True)
    submetida_em = models.DateTimeField(blank=True, null=True, editable=False)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="candidaturas_criadas",
    )
    versao = models.PositiveIntegerField("versão", default=1, editable=False)
    idempotencia_submissao = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        editable=False,
    )

    class Meta:
        verbose_name = "candidatura"
        verbose_name_plural = "candidaturas"
        ordering = ("-criado_em",)
        indexes = [
            models.Index(fields=("tipo", "estado_atual"), name="cand_tipo_estado_idx"),
            models.Index(
                fields=("titular_empresa", "estado_atual"), name="cand_empresa_estado_idx"
            ),
            models.Index(
                fields=("titular_candidato", "estado_atual"),
                name="cand_pessoa_estado_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        tipo="INDIVIDUAL",
                        titular_candidato__isnull=False,
                        titular_empresa__isnull=True,
                    )
                    | Q(
                        tipo="EMPRESARIAL",
                        titular_candidato__isnull=True,
                        titular_empresa__isnull=False,
                    )
                ),
                name="candidaturas_titular_coerente",
            ),
            models.CheckConstraint(
                condition=Q(versao__gt=0),
                name="candidaturas_versao_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {str(self.public_id)[:8]}"

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                self.__class__.objects.filter(pk=self.pk)
                .values("estado_atual", "resultado_decisao")
                .first()
            )
            if previous and (
                previous["estado_atual"] != self.estado_atual
                or previous["resultado_decisao"] != self.resultado_decisao
            ):
                raise ValidationError(
                    "O estado e o resultado só podem mudar através do serviço de workflow."
                )
        return super().save(*args, **kwargs)

    @property
    def titular(self):
        return self.titular_candidato or self.titular_empresa

    @property
    def editavel(self):
        return self.estado_atual == self.Estado.RASCUNHO

    def clean(self):
        super().clean()
        errors = {}
        individual_coerente = (
            self.tipo == self.Tipo.INDIVIDUAL
            and self.titular_candidato_id
            and not self.titular_empresa_id
        )
        empresarial_coerente = (
            self.tipo == self.Tipo.EMPRESARIAL
            and self.titular_empresa_id
            and not self.titular_candidato_id
        )
        if not (individual_coerente or empresarial_coerente):
            errors["tipo"] = "Indique exatamente o titular correspondente ao tipo."
        if self.conta_pagamento_id:
            if (
                self.tipo == self.Tipo.INDIVIDUAL
                and self.conta_pagamento.candidato_id != self.titular_candidato_id
            ):
                errors["conta_pagamento"] = "A conta deve pertencer ao candidato titular."
            if (
                self.tipo == self.Tipo.EMPRESARIAL
                and self.conta_pagamento.empresa_id != self.titular_empresa_id
            ):
                errors["conta_pagamento"] = "A conta deve pertencer à empresa titular."
        if errors:
            raise ValidationError(errors)


class AtribuicaoCandidatura(ModeloTemporal):
    class Papel(models.TextChoices):
        RESPONSAVEL = "RESPONSAVEL", "Responsável"
        COLABORADOR = "COLABORADOR", "Colaborador"
        LEITURA = "LEITURA", "Leitura"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.CASCADE,
        related_name="atribuicoes",
    )
    utilizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atribuicoes_candidatura",
    )
    papel = models.CharField(max_length=12, choices=Papel.choices)
    principal = models.BooleanField(default=False)
    ativa = models.BooleanField(default=True)
    inicio_em = models.DateTimeField()
    fim_em = models.DateTimeField(blank=True, null=True)
    atribuida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="atribuicoes_candidatura_criadas",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "atribuição de candidatura"
        verbose_name_plural = "atribuições de candidaturas"
        ordering = ("candidatura", "-principal", "utilizador")
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "utilizador"),
                condition=Q(ativa=True),
                name="candidaturas_atribuicao_ativa_unica",
            ),
            models.UniqueConstraint(
                fields=("candidatura",),
                condition=Q(ativa=True, principal=True),
                name="candidaturas_responsavel_principal_unico",
            ),
            models.CheckConstraint(
                condition=Q(fim_em__isnull=True) | Q(fim_em__gte=models.F("inicio_em")),
                name="candidaturas_atribuicao_periodo_valido",
            ),
        ]

    def __str__(self):
        return f"{self.candidatura} — {self.utilizador} ({self.get_papel_display()})"

    def clean(self):
        super().clean()
        if self.fim_em and self.fim_em < self.inicio_em:
            raise ValidationError({"fim_em": "A data final não pode ser anterior à inicial."})


class BeneficiarioCandidatura(ModeloTemporal):
    class Resultado(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        DEFERIDA = "DEFERIDA", "Deferida"
        INDEFERIDA = "INDEFERIDA", "Indeferida"
        ARQUIVADA = "ARQUIVADA", "Arquivada"
        DESISTIDA = "DESISTIDA", "Desistida"
        REVOGADA = "REVOGADA", "Revogada"
        ENCERRADA = "ENCERRADA", "Encerrada"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.CASCADE,
        related_name="beneficiarios",
    )
    candidato = models.ForeignKey(
        PerfilCandidato,
        on_delete=models.PROTECT,
        related_name="participacoes_candidatura",
    )
    e_titular = models.BooleanField(default=False)
    situacao_referencia = models.CharField(max_length=20, choices=VinculoLaboral.Situacao.choices)
    vinculo_referencia = models.ForeignKey(
        VinculoLaboral,
        on_delete=models.PROTECT,
        related_name="beneficiarios_candidatura",
        blank=True,
        null=True,
    )
    nivel_qualificacao_referencia = models.PositiveSmallIntegerField(blank=True, null=True)
    inscricao_iefp_referencia = models.DateField(blank=True, null=True)
    resultado = models.CharField(
        max_length=12,
        choices=Resultado.choices,
        default=Resultado.PENDENTE,
    )
    decidido_em = models.DateTimeField(blank=True, null=True)
    motivo_decisao = models.TextField(blank=True)
    referencia_decisao = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "beneficiário da candidatura"
        verbose_name_plural = "beneficiários da candidatura"
        ordering = ("candidatura", "candidato")
        indexes = [
            models.Index(fields=("candidatura", "resultado"), name="cand_benef_resultado_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "candidato"),
                name="candidaturas_beneficiario_unico",
            ),
            models.UniqueConstraint(
                fields=("candidatura",),
                condition=Q(e_titular=True),
                name="candidaturas_beneficiario_titular_unico",
            ),
        ]

    def __str__(self):
        return f"{self.candidatura} — {self.candidato}"

    def clean(self):
        super().clean()
        errors = {}
        if self.candidatura_id:
            if self.candidatura.tipo == Candidatura.Tipo.INDIVIDUAL:
                if self.candidato_id != self.candidatura.titular_candidato_id:
                    errors["candidato"] = "O beneficiário deve ser o candidato titular."
                if not self.e_titular:
                    errors["e_titular"] = "O beneficiário individual deve ser o titular."
            elif self.e_titular:
                errors["e_titular"] = "Uma candidatura empresarial não tem candidato titular."
        if self.vinculo_referencia_id:
            if self.vinculo_referencia.candidato_id != self.candidato_id:
                errors["vinculo_referencia"] = "O vínculo não pertence a este candidato."
            if (
                self.candidatura.tipo == Candidatura.Tipo.EMPRESARIAL
                and self.vinculo_referencia.empresa_id != self.candidatura.titular_empresa_id
            ):
                errors["vinculo_referencia"] = "O vínculo não pertence à empresa titular."
        if self.resultado not in {self.Resultado.PENDENTE, self.Resultado.DEFERIDA}:
            if not self.motivo_decisao.strip():
                errors["motivo_decisao"] = "Indique o motivo do resultado não favorável."
        if errors:
            raise ValidationError(errors)


class ParticipacaoFormacao(ModeloTemporal):
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.CASCADE,
        related_name="participacoes_formacao",
    )
    acao_formacao = models.ForeignKey(
        AcaoFormacao,
        on_delete=models.PROTECT,
        related_name="participacoes",
    )
    estado = models.CharField(
        max_length=40,
        choices=AcaoFormacao.Estado.choices,
        default=AcaoFormacao.Estado.PLANEADA,
    )
    horas_previstas = models.DecimalField(max_digits=8, decimal_places=2)
    horas_frequentadas = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
    )
    dias_tres_ou_mais_horas = models.PositiveIntegerField(blank=True, null=True)
    custo_declarado = models.DecimalField(max_digits=12, decimal_places=2)
    custo_pago_formadora = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    resultado_registado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "participação em formação"
        verbose_name_plural = "participações em formação"
        ordering = ("beneficiario", "acao_formacao")
        indexes = [
            models.Index(fields=("beneficiario", "estado"), name="cand_part_benef_estado_idx"),
            models.Index(fields=("acao_formacao", "estado"), name="cand_part_acao_estado_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("beneficiario", "acao_formacao"),
                name="candidaturas_participacao_unica",
            ),
            models.CheckConstraint(
                condition=Q(horas_previstas__gt=0),
                name="candidaturas_horas_previstas_positivas",
            ),
            models.CheckConstraint(
                condition=Q(horas_frequentadas__isnull=True) | Q(horas_frequentadas__gte=0),
                name="candidaturas_horas_frequentadas_nao_negativas",
            ),
            models.CheckConstraint(
                condition=Q(custo_declarado__gte=0),
                name="candidaturas_custo_declarado_nao_negativo",
            ),
            models.CheckConstraint(
                condition=Q(custo_pago_formadora__isnull=True) | Q(custo_pago_formadora__gte=0),
                name="candidaturas_custo_pago_nao_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.beneficiario.candidato} — {self.acao_formacao}"

    def clean(self):
        super().clean()
        errors = {}
        if self.horas_previstas is not None and self.horas_previstas <= 0:
            errors["horas_previstas"] = "As horas previstas devem ser superiores a zero."
        if self.horas_frequentadas is not None and self.horas_frequentadas < 0:
            errors["horas_frequentadas"] = "As horas frequentadas não podem ser negativas."
        if self.custo_declarado is not None and self.custo_declarado < 0:
            errors["custo_declarado"] = "O custo declarado não pode ser negativo."
        if self.custo_pago_formadora is not None and self.custo_pago_formadora < 0:
            errors["custo_pago_formadora"] = "O custo pago não pode ser negativo."
        if (
            self.acao_formacao_id
            and self.horas_previstas is not None
            and self.horas_previstas > self.acao_formacao.horas_totais
        ):
            errors["horas_previstas"] = "As horas previstas excedem a carga horária da ação."
        if errors:
            raise ValidationError(errors)


class VerificacaoElegibilidade(ModeloTemporal):
    class TipoAvaliacao(models.TextChoices):
        AUTOMATICA = "AUTOMATICA", "Automática"
        MANUAL = "MANUAL", "Manual"
        EXTERNA = "EXTERNA", "Externa"

    class Resultado(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONFORME = "CONFORME", "Conforme"
        NAO_CONFORME = "NAO_CONFORME", "Não conforme"
        NAO_APLICAVEL = "NAO_APLICAVEL", "Não aplicável"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.CASCADE,
        related_name="verificacoes_elegibilidade",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.CASCADE,
        related_name="verificacoes_elegibilidade",
        blank=True,
        null=True,
    )
    participacao = models.ForeignKey(
        ParticipacaoFormacao,
        on_delete=models.CASCADE,
        related_name="verificacoes_elegibilidade",
        blank=True,
        null=True,
    )
    codigo_regra = models.CharField("código da regra", max_length=40)
    tipo_avaliacao = models.CharField(max_length=10, choices=TipoAvaliacao.choices)
    resultado = models.CharField(max_length=14, choices=Resultado.choices)
    valor_avaliado = models.JSONField(encoder=DjangoJSONEncoder, blank=True, null=True)
    observacoes = models.TextField("observações", blank=True)
    verificada_em = models.DateTimeField(blank=True, null=True)
    verificada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verificacoes_elegibilidade_realizadas",
        blank=True,
        null=True,
    )
    evidencia = models.ForeignKey(
        "documentos.VersaoDocumento",
        on_delete=models.PROTECT,
        related_name="verificacoes_elegibilidade_comprovadas",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "verificação de elegibilidade"
        verbose_name_plural = "verificações de elegibilidade"
        ordering = ("candidatura", "codigo_regra", "beneficiario", "participacao")
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "codigo_regra"),
                condition=Q(beneficiario__isnull=True, participacao__isnull=True),
                name="candidaturas_verificacao_global_unica",
            ),
            models.UniqueConstraint(
                fields=("beneficiario", "codigo_regra"),
                condition=Q(beneficiario__isnull=False, participacao__isnull=True),
                name="candidaturas_verificacao_benef_unica",
            ),
            models.UniqueConstraint(
                fields=("participacao", "codigo_regra"),
                condition=Q(participacao__isnull=False),
                name="candidaturas_verificacao_part_unica",
            ),
        ]

    def __str__(self):
        return f"{self.codigo_regra} — {self.get_resultado_display()}"

    def save(self, *args, **kwargs):
        self.codigo_regra = self.codigo_regra.strip().upper()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.codigo_regra = self.codigo_regra.strip().upper()
        errors = {}
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if self.participacao_id:
            if self.participacao.beneficiario.candidatura_id != self.candidatura_id:
                errors["participacao"] = "A participação não pertence à candidatura."
            if self.beneficiario_id != self.participacao.beneficiario_id:
                errors["beneficiario"] = "A participação deve corresponder ao beneficiário."
        if self.tipo_avaliacao == self.TipoAvaliacao.AUTOMATICA and self.verificada_por_id:
            errors["verificada_por"] = "Uma verificação automática não tem autor manual."
        if errors:
            raise ValidationError(errors)
