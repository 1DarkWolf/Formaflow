from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura
from apps.core.models import ModeloTemporal
from apps.documentos.models import RequisitoDocumento, SnapshotSubmissao, VersaoDocumento
from apps.regras.models import ConjuntoRegras, TipoDocumento


class TransicaoCandidatura(models.Model):
    class Origem(models.TextChoices):
        UTILIZADOR = "UTILIZADOR", "Utilizador"
        SISTEMA = "SISTEMA", "Sistema"
        IEFPONLINE = "IEFPONLINE", "Iefponline"
        COMUNICACAO_IEFP = "COMUNICACAO_IEFP", "Comunicação do IEFP"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="transicoes",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.PROTECT,
        related_name="transicoes",
        blank=True,
        null=True,
    )
    codigo = models.CharField("código", max_length=10)
    estado_anterior = models.CharField(  # noqa: DJ001
        max_length=40,
        choices=Candidatura.Estado.choices,
        blank=True,
        null=True,
    )
    estado_novo = models.CharField(max_length=40, choices=Candidatura.Estado.choices)
    efetiva_em = models.DateTimeField()
    registada_em = models.DateTimeField(auto_now_add=True, editable=False)
    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="transicoes_candidatura_registadas",
        blank=True,
        null=True,
    )
    origem = models.CharField(max_length=16, choices=Origem.choices)
    referencia_externa = models.CharField("referência externa", max_length=100, blank=True)
    motivo = models.TextField(blank=True)
    evidencia = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="transicoes_comprovadas",
        blank=True,
        null=True,
    )
    conjunto_regras = models.ForeignKey(
        ConjuntoRegras,
        on_delete=models.PROTECT,
        related_name="transicoes_candidatura",
    )
    versao_anterior = models.PositiveIntegerField(editable=False)
    versao_nova = models.PositiveIntegerField(editable=False)
    corrige_transicao = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="correcoes",
        blank=True,
        null=True,
    )
    chave_idempotencia = models.CharField(max_length=100)

    class Meta:
        verbose_name = "transição de candidatura"
        verbose_name_plural = "transições de candidaturas"
        ordering = ("candidatura", "registada_em", "pk")
        indexes = [
            models.Index(
                fields=("candidatura", "registada_em"), name="workflow_transicao_hist_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "chave_idempotencia"),
                name="workflow_transicao_idempotencia_unica",
            ),
            models.CheckConstraint(
                condition=Q(versao_nova=models.F("versao_anterior") + 1),
                name="workflow_transicao_versao_sequencial",
            ),
            models.CheckConstraint(
                condition=(Q(codigo="TR-001", estado_anterior__isnull=True))
                | (~Q(codigo="TR-001") & Q(estado_anterior__isnull=False)),
                name="workflow_transicao_origem_coerente",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.get_estado_novo_display()}"

    def save(self, *args, **kwargs):
        if self.pk and self.__class__.objects.filter(pk=self.pk).exists():
            raise ValidationError("Uma transição é imutável; registe uma correção.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Uma transição não pode ser eliminada.")

    def clean(self):
        super().clean()
        errors = {}
        self.codigo = self.codigo.strip().upper()
        self.chave_idempotencia = self.chave_idempotencia.strip()
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if self.evidencia_id and self.evidencia.documento.candidatura_id != self.candidatura_id:
            errors["evidencia"] = "A evidência não pertence à candidatura."
        if self.versao_nova != self.versao_anterior + 1:
            errors["versao_nova"] = "A versão nova deve avançar exatamente uma unidade."
        if (
            self.codigo
            in {
                "TR-005",
                "TR-010",
                "TR-011",
                "TR-012",
                "TR-014",
                "TR-022",
                "TR-023",
            }
            and not self.motivo.strip()
        ):
            errors["motivo"] = "Esta transição exige um motivo."
        if not self.chave_idempotencia:
            errors["chave_idempotencia"] = "Indique uma chave de idempotência."
        if errors:
            raise ValidationError(errors)


class PedidoElementos(ModeloTemporal):
    class Fase(models.TextChoices):
        ANALISE = "ANALISE", "Análise"
        ENCERRAMENTO = "ENCERRAMENTO", "Encerramento"

    class Estado(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        RESPOSTA_RASCUNHO = "RESPOSTA_RASCUNHO", "Resposta em rascunho"
        RESPONDIDO = "RESPONDIDO", "Respondido"
        FECHADO = "FECHADO", "Fechado"
        EXPIRADO = "EXPIRADO", "Expirado"
        CANCELADO = "CANCELADO", "Cancelado"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="pedidos_elementos",
    )
    fase = models.CharField(max_length=12, choices=Fase.choices)
    referencia_externa = models.CharField("referência externa", max_length=100, blank=True)
    recebido_em = models.DateTimeField()
    data_limite = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABERTO)
    descricao = models.TextField("descrição", blank=True)
    evidencia = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="pedidos_elementos_comprovados",
        blank=True,
        null=True,
    )
    registado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos_elementos_registados",
    )
    fechado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "pedido de elementos"
        verbose_name_plural = "pedidos de elementos"
        ordering = ("-recebido_em", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("candidatura", "referencia_externa"),
                condition=~Q(referencia_externa=""),
                name="workflow_pedido_referencia_unica",
            ),
            models.CheckConstraint(
                condition=Q(data_limite__gte=models.F("recebido_em")),
                name="workflow_pedido_limite_valido",
            ),
        ]

    def __str__(self):
        return f"Pedido {self.pk or 'novo'} — {self.get_estado_display()}"

    def clean(self):
        super().clean()
        errors = {}
        if self.data_limite and self.recebido_em and self.data_limite < self.recebido_em:
            errors["data_limite"] = "O limite não pode anteceder a receção."
        if self.evidencia_id and self.evidencia.documento.candidatura_id != self.candidatura_id:
            errors["evidencia"] = "A evidência não pertence à candidatura."
        if self.estado == self.Estado.FECHADO and not self.fechado_em:
            errors["fechado_em"] = "Indique quando o pedido foi fechado."
        if errors:
            raise ValidationError(errors)


class QuestaoPedido(models.Model):
    class Destinatario(models.TextChoices):
        TITULAR = "TITULAR", "Titular"
        BENEFICIARIO = "BENEFICIARIO", "Beneficiário"
        EMPRESA = "EMPRESA", "Empresa"
        FORMADORA = "FORMADORA", "Entidade formadora"
        GESTOR = "GESTOR", "Gestor"

    pedido = models.ForeignKey(
        PedidoElementos,
        on_delete=models.PROTECT,
        related_name="questoes",
    )
    ordem = models.PositiveIntegerField()
    texto = models.TextField()
    destinatario = models.CharField(max_length=14, choices=Destinatario.choices)
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.PROTECT,
        related_name="questoes_pedido",
        blank=True,
        null=True,
    )
    exige_texto = models.BooleanField(default=True)
    exige_documento = models.BooleanField(default=False)
    tipo_documento_pedido = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name="questoes_pedido",
        blank=True,
        null=True,
    )
    obrigatoria = models.BooleanField(default=True)

    class Meta:
        verbose_name = "questão de pedido"
        verbose_name_plural = "questões de pedidos"
        ordering = ("pedido", "ordem")
        constraints = [
            models.UniqueConstraint(
                fields=("pedido", "ordem"),
                name="workflow_questao_ordem_unica",
            ),
            models.CheckConstraint(
                condition=Q(ordem__gt=0),
                name="workflow_questao_ordem_positiva",
            ),
            models.CheckConstraint(
                condition=Q(exige_texto=True) | Q(exige_documento=True),
                name="workflow_questao_exigencia_presente",
            ),
        ]

    def __str__(self):
        return f"{self.ordem}. {self.texto[:80]}"

    def clean(self):
        super().clean()
        errors = {}
        if not self.texto.strip():
            errors["texto"] = "A questão não pode ficar vazia."
        if self.destinatario == self.Destinatario.BENEFICIARIO and not self.beneficiario_id:
            errors["beneficiario"] = "Indique o beneficiário destinatário."
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.pedido.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if not self.exige_texto and not self.exige_documento:
            errors["exige_texto"] = "A questão deve exigir texto ou documento."
        if self.exige_documento and not self.tipo_documento_pedido_id:
            errors["tipo_documento_pedido"] = "Indique o tipo de documento pedido."
        if errors:
            raise ValidationError(errors)


class RespostaQuestao(models.Model):
    class Estado(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        SUBMETIDA = "SUBMETIDA", "Submetida"
        SUBSTITUIDA = "SUBSTITUIDA", "Substituída"

    questao = models.ForeignKey(
        QuestaoPedido,
        on_delete=models.PROTECT,
        related_name="respostas",
    )
    numero = models.PositiveIntegerField(editable=False)
    texto = models.TextField(blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.RASCUNHO)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="respostas_questoes",
    )
    criada_em = models.DateTimeField(auto_now_add=True, editable=False)
    submetida_em = models.DateTimeField(blank=True, null=True, editable=False)
    versoes_documentos = models.ManyToManyField(
        VersaoDocumento,
        related_name="respostas_questoes",
        blank=True,
    )

    class Meta:
        verbose_name = "resposta a questão"
        verbose_name_plural = "respostas a questões"
        ordering = ("questao", "-numero")
        constraints = [
            models.UniqueConstraint(
                fields=("questao", "numero"),
                name="workflow_resposta_numero_unico",
            ),
            models.UniqueConstraint(
                fields=("questao",),
                condition=Q(estado="SUBMETIDA"),
                name="workflow_resposta_submetida_unica",
            ),
            models.CheckConstraint(
                condition=Q(numero__gt=0),
                name="workflow_resposta_numero_positivo",
            ),
        ]

    def __str__(self):
        return f"Resposta {self.questao_id}.{self.numero}"

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.estado == self.Estado.SUBMETIDA
            and self.questao.exige_texto
            and not self.texto.strip()
        ):
            errors["texto"] = "Esta questão exige uma resposta textual."
        if self.estado == self.Estado.SUBMETIDA and not self.submetida_em:
            errors["submetida_em"] = "Uma resposta submetida exige data."
        if errors:
            raise ValidationError(errors)


class TermoAceitacao(ModeloTemporal):
    class Estado(models.TextChoices):
        NAO_APLICAVEL = "NAO_APLICAVEL", "Não aplicável"
        PENDENTE = "PENDENTE", "Pendente"
        RECEBIDO = "RECEBIDO", "Recebido"
        VALIDADO = "VALIDADO", "Validado"
        INVALIDO = "INVALIDO", "Inválido"
        FORA_PRAZO = "FORA_PRAZO", "Fora de prazo"
        DISPENSADO = "DISPENSADO", "Dispensado com justificação"

    class TipoAssinatura(models.TextChoices):
        MANUSCRITA = "MANUSCRITA", "Manuscrita"
        DIGITAL_PESSOAL = "DIGITAL_PESSOAL", "Digital pessoal"
        DIGITAL_PROFISSIONAL_SCAP = "DIGITAL_PROFISSIONAL_SCAP", "Digital profissional SCAP"
        OUTRA = "OUTRA", "Outra"

    candidatura = models.OneToOneField(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="termo_aceitacao",
    )
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.NAO_APLICAVEL)
    notificado_em = models.DateTimeField(blank=True, null=True)
    data_limite = models.DateTimeField(blank=True, null=True)
    recebido_em = models.DateTimeField(blank=True, null=True)
    validado_em = models.DateTimeField(blank=True, null=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="termos_aceitacao_validados",
        blank=True,
        null=True,
    )
    tipo_assinatura = models.CharField(
        max_length=26,
        choices=TipoAssinatura.choices,
        blank=True,
    )
    fora_prazo = models.BooleanField(default=False, editable=False)
    documento = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="termos_aceitacao",
        blank=True,
        null=True,
    )
    justificacao = models.TextField("justificação", blank=True)

    class Meta:
        verbose_name = "termo de aceitação"
        verbose_name_plural = "termos de aceitação"

    def __str__(self):
        return f"Termo — {self.candidatura}"


class PedidoEncerramento(ModeloTemporal):
    class Estado(models.TextChoices):
        PREPARACAO = "PREPARACAO", "Preparação"
        SUBMETIDO = "SUBMETIDO", "Submetido"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        AGUARDA_ELEMENTOS = "AGUARDA_ELEMENTOS", "Aguarda elementos"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        NAO_ACEITE = "NAO_ACEITE", "Não aceite"

    class ResultadoFinal(models.TextChoices):
        CONCLUIDO = "CONCLUIDO", "Concluído"
        CONCLUIDO_PARCIAL = "CONCLUIDO_PARCIAL", "Concluído parcialmente"
        NAO_ACEITE = "NAO_ACEITE", "Não aceite"
        OUTRO = "OUTRO", "Outro"

    candidatura = models.OneToOneField(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="pedido_encerramento",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PREPARACAO)
    preparacao_iniciada_em = models.DateTimeField()
    submetido_em = models.DateTimeField(blank=True, null=True)
    analise_iniciada_em = models.DateTimeField(blank=True, null=True)
    concluido_em = models.DateTimeField(blank=True, null=True)
    referencia_externa = models.CharField("referência externa", max_length=100, blank=True)
    resultado_final = models.CharField(max_length=20, choices=ResultadoFinal.choices, blank=True)
    observacoes_decisao = models.TextField("observações da decisão", blank=True)
    snapshot_submissao = models.ForeignKey(
        SnapshotSubmissao,
        on_delete=models.PROTECT,
        related_name="pedidos_encerramento",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "pedido de encerramento"
        verbose_name_plural = "pedidos de encerramento"

    def __str__(self):
        return f"Encerramento — {self.candidatura}"


class Prazo(ModeloTemporal):
    class Tipo(models.TextChoices):
        DECISAO = "DECISAO", "Decisão"
        RESPOSTA_ELEMENTOS = "RESPOSTA_ELEMENTOS", "Resposta a elementos"
        TERMO = "TERMO", "Termo"
        PRIMEIRA_PRESTACAO = "PRIMEIRA_PRESTACAO", "Primeira prestação"
        REMANESCENTE = "REMANESCENTE", "Remanescente"
        ENCERRAMENTO = "ENCERRAMENTO", "Encerramento"
        RESTITUICAO = "RESTITUICAO", "Restituição"
        OUTRO = "OUTRO", "Outro"

    class Unidade(models.TextChoices):
        DIAS_UTEIS = "DIAS_UTEIS", "Dias úteis"
        DIAS_CONSECUTIVOS = "DIAS_CONSECUTIVOS", "Dias consecutivos"
        MESES = "MESES", "Meses"
        ANOS = "ANOS", "Anos"

    class Estado(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        SUSPENSO = "SUSPENSO", "Suspenso"
        CUMPRIDO = "CUMPRIDO", "Cumprido"
        EXPIRADO = "EXPIRADO", "Expirado"
        CANCELADO = "CANCELADO", "Cancelado"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="prazos",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.PROTECT,
        related_name="prazos",
        blank=True,
        null=True,
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    codigo_regra = models.CharField("código da regra", max_length=40)
    conjunto_regras = models.ForeignKey(
        ConjuntoRegras,
        on_delete=models.PROTECT,
        related_name="prazos",
    )
    inicio_em = models.DateTimeField()
    unidade = models.CharField(max_length=20, choices=Unidade.choices)
    duracao = models.DecimalField("duração", max_digits=8, decimal_places=2)
    limite_calculado = models.DateTimeField()
    limite_oficial = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ATIVO)
    transicao_origem = models.ForeignKey(
        TransicaoCandidatura,
        on_delete=models.PROTECT,
        related_name="prazos_criados",
        blank=True,
        null=True,
    )
    corrigido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="prazos_corrigidos",
        blank=True,
        null=True,
    )
    motivo_correcao = models.TextField("motivo da correção", blank=True)
    limite_anterior = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "prazo"
        verbose_name_plural = "prazos"
        ordering = ("limite_calculado", "pk")
        indexes = [
            models.Index(fields=("estado", "limite_calculado"), name="workflow_prazo_alerta_idx"),
            models.Index(fields=("estado", "limite_oficial"), name="workflow_prazo_oficial_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(duracao__gt=0),
                name="workflow_prazo_duracao_positiva",
            ),
            models.CheckConstraint(
                condition=Q(limite_calculado__gte=models.F("inicio_em")),
                name="workflow_prazo_limite_valido",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.limite_efetivo:%d/%m/%Y}"

    @property
    def limite_efetivo(self):
        return self.limite_oficial or self.limite_calculado

    def clean(self):
        super().clean()
        errors = {}
        if self.duracao is not None and self.duracao <= 0:
            errors["duracao"] = "A duração deve ser positiva."
        if self.limite_calculado and self.inicio_em and self.limite_calculado < self.inicio_em:
            errors["limite_calculado"] = "O limite não pode anteceder o início."
        correction_fields = (self.corrigido_por_id, self.motivo_correcao, self.limite_anterior)
        if any(correction_fields) and not all(correction_fields):
            errors["motivo_correcao"] = "A correção exige autor, motivo e limite anterior."
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if errors:
            raise ValidationError(errors)


class SuspensaoPrazo(models.Model):
    class Origem(models.TextChoices):
        CALCULADA = "CALCULADA", "Calculada"
        OFICIAL = "OFICIAL", "Oficial"
        CORRECAO_MANUAL = "CORRECAO_MANUAL", "Correção manual"

    prazo = models.ForeignKey(Prazo, on_delete=models.PROTECT, related_name="suspensoes")
    pedido_elementos = models.ForeignKey(
        PedidoElementos,
        on_delete=models.PROTECT,
        related_name="suspensoes_prazo",
        blank=True,
        null=True,
    )
    inicio_em = models.DateTimeField()
    fim_em = models.DateTimeField(blank=True, null=True)
    origem = models.CharField(max_length=16, choices=Origem.choices)
    motivo = models.TextField()
    registada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="suspensoes_prazo_registadas",
        blank=True,
        null=True,
    )
    registada_em = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = "suspensão de prazo"
        verbose_name_plural = "suspensões de prazos"
        ordering = ("prazo", "inicio_em")
        constraints = [
            models.UniqueConstraint(
                fields=("prazo",),
                condition=Q(fim_em__isnull=True),
                name="workflow_suspensao_aberta_unica",
            ),
            models.CheckConstraint(
                condition=Q(fim_em__isnull=True) | Q(fim_em__gte=models.F("inicio_em")),
                name="workflow_suspensao_periodo_valido",
            ),
        ]

    def __str__(self):
        return f"Suspensão desde {self.inicio_em:%d/%m/%Y}"

    def clean(self):
        super().clean()
        errors = {}
        if self.fim_em and self.fim_em < self.inicio_em:
            errors["fim_em"] = "O fim da suspensão não pode anteceder o início."
        if (
            self.pedido_elementos_id
            and self.pedido_elementos.candidatura_id != self.prazo.candidatura_id
        ):
            errors["pedido_elementos"] = "O pedido não pertence à candidatura do prazo."
        if not self.motivo.strip():
            errors["motivo"] = "Indique o motivo da suspensão."
        if errors:
            raise ValidationError(errors)


class Tarefa(ModeloTemporal):
    class Estado(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        EM_EXECUCAO = "EM_EXECUCAO", "Em execução"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    class Prioridade(models.TextChoices):
        BAIXA = "BAIXA", "Baixa"
        NORMAL = "NORMAL", "Normal"
        ALTA = "ALTA", "Alta"
        CRITICA = "CRITICA", "Crítica"

    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="tarefas",
    )
    beneficiario = models.ForeignKey(
        BeneficiarioCandidatura,
        on_delete=models.PROTECT,
        related_name="tarefas",
        blank=True,
        null=True,
    )
    atribuida_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tarefas_atribuidas",
        blank=True,
        null=True,
    )
    tipo = models.CharField(max_length=80)
    titulo = models.CharField("título", max_length=255)
    descricao = models.TextField("descrição", blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ABERTA)
    prioridade = models.CharField(
        max_length=8,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
    )
    data_limite = models.DateTimeField(blank=True, null=True)
    concluida_em = models.DateTimeField(blank=True, null=True)
    concluida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tarefas_concluidas",
        blank=True,
        null=True,
    )
    prazo_origem = models.ForeignKey(
        Prazo,
        on_delete=models.PROTECT,
        related_name="tarefas",
        blank=True,
        null=True,
    )
    requisito_origem = models.ForeignKey(
        RequisitoDocumento,
        on_delete=models.PROTECT,
        related_name="tarefas",
        blank=True,
        null=True,
    )
    pedido_origem = models.ForeignKey(
        PedidoElementos,
        on_delete=models.PROTECT,
        related_name="tarefas",
        blank=True,
        null=True,
    )
    termo_origem = models.ForeignKey(
        TermoAceitacao,
        on_delete=models.PROTECT,
        related_name="tarefas",
        blank=True,
        null=True,
    )
    encerramento_origem = models.ForeignKey(
        PedidoEncerramento,
        on_delete=models.PROTECT,
        related_name="tarefas",
        blank=True,
        null=True,
    )
    chave_deduplicacao = models.CharField(  # noqa: DJ001
        max_length=150,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "tarefa"
        verbose_name_plural = "tarefas"
        ordering = ("-prioridade", "data_limite", "pk")
        indexes = [
            models.Index(
                fields=("atribuida_a", "estado", "data_limite"),
                name="workflow_tarefa_painel_idx",
            ),
            models.Index(
                fields=("candidatura", "estado", "data_limite"),
                name="workflow_tarefa_cand_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("chave_deduplicacao",),
                condition=Q(
                    chave_deduplicacao__isnull=False,
                    estado__in=("ABERTA", "EM_EXECUCAO"),
                ),
                name="workflow_tarefa_dedup_ativa",
            ),
        ]

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        errors = {}
        origins = (
            self.prazo_origem_id,
            self.requisito_origem_id,
            self.pedido_origem_id,
            self.termo_origem_id,
            self.encerramento_origem_id,
        )
        if sum(bool(item) for item in origins) > 1:
            errors["tipo"] = "Uma tarefa automática deve ter no máximo uma origem."
        if self.estado == self.Estado.CONCLUIDA and (
            not self.concluida_em or not self.concluida_por_id
        ):
            errors["estado"] = "Uma tarefa concluída exige autor e data."
        if self.beneficiario_id and self.beneficiario.candidatura_id != self.candidatura_id:
            errors["beneficiario"] = "O beneficiário não pertence à candidatura."
        if errors:
            raise ValidationError(errors)


class Notificacao(ModeloTemporal):
    class Prioridade(models.TextChoices):
        INFORMATIVA = "INFORMATIVA", "Informativa"
        ATENCAO = "ATENCAO", "Atenção"
        URGENTE = "URGENTE", "Urgente"
        CRITICA = "CRITICA", "Crítica"

    class Estado(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ENVIADA = "ENVIADA", "Enviada"
        LIDA = "LIDA", "Lida"
        RESOLVIDA = "RESOLVIDA", "Resolvida"
        FALHOU = "FALHOU", "Falhou"

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notificacoes",
    )
    candidatura = models.ForeignKey(
        Candidatura,
        on_delete=models.PROTECT,
        related_name="notificacoes",
        blank=True,
        null=True,
    )
    tarefa = models.ForeignKey(
        Tarefa,
        on_delete=models.PROTECT,
        related_name="notificacoes",
        blank=True,
        null=True,
    )
    prazo = models.ForeignKey(
        Prazo,
        on_delete=models.PROTECT,
        related_name="notificacoes",
        blank=True,
        null=True,
    )
    codigo = models.CharField("código", max_length=80)
    titulo = models.CharField("título", max_length=255)
    mensagem = models.TextField()
    prioridade = models.CharField(
        max_length=12,
        choices=Prioridade.choices,
        default=Prioridade.INFORMATIVA,
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDENTE)
    limiar = models.CharField(max_length=40, blank=True)
    chave_deduplicacao = models.CharField(max_length=180)
    enviada_em = models.DateTimeField(blank=True, null=True)
    lida_em = models.DateTimeField(blank=True, null=True)
    resolvida_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        ordering = ("-criado_em",)
        indexes = [
            models.Index(
                fields=("destinatario", "estado", "criado_em"),
                name="workflow_notif_painel_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("destinatario", "chave_deduplicacao"),
                name="workflow_notificacao_dedup_unica",
            ),
        ]

    def __str__(self):
        return self.titulo
