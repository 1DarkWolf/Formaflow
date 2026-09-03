import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura
from apps.documentos.models import VersaoDocumento
from apps.formacoes.models import AcaoFormacao
from apps.regras.models import TipoDocumento

from .models import PedidoEncerramento, TermoAceitacao


class FormularioWorkflowBase(forms.Form):
    versao = forms.IntegerField(widget=forms.HiddenInput)
    chave_idempotencia = forms.CharField(max_length=100, widget=forms.HiddenInput)

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidatura = candidatura
        self.fields["versao"].initial = candidatura.versao
        self.fields["chave_idempotencia"].initial = uuid.uuid4().hex


class FormularioDocumentoWorkflow(forms.Form):
    tipo_documento = forms.ModelChoiceField(
        label="Tipo de documento",
        queryset=TipoDocumento.objects.none(),
    )
    titulo = forms.CharField(label="Título", max_length=255, required=False)
    ficheiro = forms.FileField(
        label="Ficheiro PDF",
        help_text="O documento fica privado e sujeito ao limite definido nas regras.",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,.pdf"}),
    )

    def __init__(self, *args, tipo_documento=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = TipoDocumento.objects.filter(ativo=True)
        if tipo_documento:
            queryset = queryset.filter(pk=tipo_documento.pk)
            self.fields["tipo_documento"].initial = tipo_documento
            self.fields["tipo_documento"].widget = forms.HiddenInput()
        self.fields["tipo_documento"].queryset = queryset


class FormularioAcontecimento(FormularioWorkflowBase):
    efetiva_em = forms.DateTimeField(
        label="Data e hora efetivas",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    referencia_externa = forms.CharField(
        label="Referência externa",
        max_length=100,
        required=False,
    )
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
        help_text="Selecione uma versão já guardada nesta candidatura, quando aplicável.",
    )
    motivo = forms.CharField(
        label="Motivo",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    avisos_reconhecidos = forms.BooleanField(
        label="Revisei a candidatura e reconheço os avisos apresentados.",
        required=False,
    )
    confirmacao = forms.BooleanField(
        label="Confirmo que este acontecimento ocorreu e que os dados estão corretos.",
    )

    def __init__(self, *args, candidatura, codigo, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        self.codigo = codigo
        local_now = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["efetiva_em"].initial = local_now.strftime("%Y-%m-%dT%H:%M:%S")
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura,
            corrente=True,
        ).select_related("documento__tipo_documento")
        if codigo != "TR-002":
            self.fields.pop("avisos_reconhecidos")
        if codigo in {"TR-003"}:
            self.fields.pop("referencia_externa")
            self.fields.pop("evidencia")
            self.fields.pop("motivo")
        if codigo in {"TR-005", "TR-012", "TR-014", "TR-022"}:
            self.fields["motivo"].required = True


class FormularioPedidoElementos(FormularioWorkflowBase):
    recebido_em = forms.DateTimeField(
        label="Recebido em",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    referencia_externa = forms.CharField(
        label="Referência do pedido",
        max_length=100,
        required=False,
    )
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
    )
    descricao = forms.CharField(
        label="Descrição geral",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    questoes = forms.CharField(
        label="Questões pedidas",
        help_text="Escreva uma questão por linha.",
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    confirmacao = forms.BooleanField(
        label="Confirmo que transcrevi o pedido externo corretamente.",
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        local_now = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["recebido_em"].initial = local_now.strftime("%Y-%m-%dT%H:%M:%S")
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura,
            corrente=True,
        ).select_related("documento__tipo_documento")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("referencia_externa", "").strip() and not cleaned.get("evidencia"):
            raise ValidationError("Indique a referência do pedido ou associe uma evidência.")
        lines = [line.strip() for line in cleaned.get("questoes", "").splitlines() if line.strip()]
        if not lines:
            self.add_error("questoes", "Indique pelo menos uma questão.")
        cleaned["questoes_normalizadas"] = lines
        return cleaned


class FormularioResposta(forms.Form):
    texto = forms.CharField(
        label="Resposta",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    versoes_documentos = forms.ModelMultipleChoiceField(
        label="Documentos anexos",
        queryset=VersaoDocumento.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, questao, **kwargs):
        super().__init__(*args, **kwargs)
        self.questao = questao
        versions = VersaoDocumento.objects.filter(
            documento__candidatura=questao.pedido.candidatura,
            corrente=True,
        ).select_related("documento__tipo_documento")
        if questao.tipo_documento_pedido_id:
            versions = versions.filter(
                documento__tipo_documento_id=questao.tipo_documento_pedido_id
            )
        self.fields["versoes_documentos"].queryset = versions
        current = questao.respostas.exclude(estado="SUBSTITUIDA").order_by("-numero").first()
        if current and not self.is_bound:
            self.fields["texto"].initial = current.texto
            self.fields["versoes_documentos"].initial = current.versoes_documentos.all()


class FormularioRespostaCompleta(FormularioWorkflowBase):
    efetiva_em = forms.DateTimeField(
        label="Resposta enviada em",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    confirmacao = forms.BooleanField(
        label="Confirmo que a resposta completa foi enviada no Iefponline.",
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        local_now = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["efetiva_em"].initial = local_now.strftime("%Y-%m-%dT%H:%M:%S")


class FormularioDecisao(FormularioWorkflowBase):
    efetiva_em = forms.DateTimeField(
        label="Decisão comunicada em",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    referencia_externa = forms.CharField(
        label="Referência da decisão",
        max_length=100,
        required=False,
    )
    evidencia = forms.ModelChoiceField(
        label="Comunicação que comprova a decisão",
        queryset=VersaoDocumento.objects.none(),
        required=True,
    )
    motivo = forms.CharField(
        label="Motivo global, se aplicável",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    confirmacao = forms.BooleanField(
        label="Confirmo que a decisão corresponde à comunicação oficial.",
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        local_now = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["efetiva_em"].initial = local_now.strftime("%Y-%m-%dT%H:%M:%S")
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura,
            corrente=True,
        ).select_related("documento__tipo_documento")
        result_choices = (
            (BeneficiarioCandidatura.Resultado.DEFERIDA, "Deferida"),
            (BeneficiarioCandidatura.Resultado.INDEFERIDA, "Indeferida"),
            (BeneficiarioCandidatura.Resultado.ARQUIVADA, "Arquivada"),
        )
        for beneficiary in candidatura.beneficiarios.select_related(
            "candidato__utilizador"
        ).order_by("pk"):
            suffix = str(beneficiary.pk)
            self.fields[f"resultado_{suffix}"] = forms.ChoiceField(
                label=f"Resultado — {beneficiary.candidato}",
                choices=result_choices,
            )
            self.fields[f"motivo_{suffix}"] = forms.CharField(
                label=f"Motivo individual — {beneficiary.candidato}",
                required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
            )

    def resultados(self):
        return {
            beneficiary.pk: self.cleaned_data[f"resultado_{beneficiary.pk}"]
            for beneficiary in self.candidatura.beneficiarios.order_by("pk")
        }

    def motivos_beneficiarios(self):
        return {
            beneficiary.pk: self.cleaned_data[f"motivo_{beneficiary.pk}"]
            for beneficiary in self.candidatura.beneficiarios.order_by("pk")
        }


class FormularioConfirmacaoWorkflow(FormularioWorkflowBase):
    efetiva_em = forms.DateTimeField(
        label="Data e hora efetivas",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    confirmacao = forms.BooleanField(label="Confirmo que os dados estão corretos.")

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        local_now = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["efetiva_em"].initial = local_now.strftime("%Y-%m-%dT%H:%M:%S")


class FormularioTermoRecebido(forms.Form):
    versao = forms.IntegerField(widget=forms.HiddenInput)
    documento = forms.ModelChoiceField(
        label="Termo de aceitação",
        queryset=VersaoDocumento.objects.none(),
    )
    recebido_em = forms.DateTimeField(
        label="Recebido em",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    tipo_assinatura = forms.ChoiceField(
        label="Tipo de assinatura",
        choices=TermoAceitacao.TipoAssinatura.choices,
    )
    justificacao = forms.CharField(
        label="Observação ou justificação",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["versao"].initial = candidatura.versao
        local_now = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["recebido_em"].initial = local_now.strftime("%Y-%m-%dT%H:%M:%S")
        self.fields["documento"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura,
            documento__tipo_documento__codigo="TERMO_ACEITACAO",
            corrente=True,
        ).select_related("documento__tipo_documento")


class FormularioParticipacao(forms.Form):
    estado = forms.ChoiceField(label="Novo estado", choices=AcaoFormacao.Estado.choices)
    inicio_real = forms.DateField(
        label="Início real",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fim_real = forms.DateField(
        label="Fim real",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    horas_frequentadas = forms.DecimalField(
        label="Horas frequentadas", min_value=0, decimal_places=2, required=False
    )
    dias_tres_ou_mais_horas = forms.IntegerField(
        label="Dias com três ou mais horas", min_value=0, required=False
    )
    custo_pago_formadora = forms.DecimalField(
        label="Custo pago à formadora", min_value=0, decimal_places=2, required=False
    )
    motivo = forms.CharField(
        label="Motivo da interrupção ou cancelamento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, participacao, **kwargs):
        super().__init__(*args, **kwargs)
        action = participacao.acao_formacao
        if not self.is_bound:
            self.initial.update(
                {
                    "inicio_real": action.inicio_real,
                    "fim_real": action.fim_real,
                    "horas_frequentadas": participacao.horas_frequentadas,
                    "dias_tres_ou_mais_horas": participacao.dias_tres_ou_mais_horas,
                    "custo_pago_formadora": participacao.custo_pago_formadora,
                    "motivo": participacao.motivo_resultado,
                }
            )


class FormularioSubmissaoEncerramento(FormularioConfirmacaoWorkflow):
    referencia_externa = forms.CharField(label="Referência externa", max_length=100)
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
    )
    motivo_atraso = forms.CharField(
        label="Justificação se a submissão está fora de prazo",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura,
            corrente=True,
        ).select_related("documento__tipo_documento")


class FormularioConclusaoEncerramento(FormularioConfirmacaoWorkflow):
    resultado_final = forms.ChoiceField(
        label="Resultado final",
        choices=(
            (
                PedidoEncerramento.ResultadoFinal.CONCLUIDO,
                PedidoEncerramento.ResultadoFinal.CONCLUIDO.label,
            ),
            (
                PedidoEncerramento.ResultadoFinal.CONCLUIDO_PARCIAL,
                PedidoEncerramento.ResultadoFinal.CONCLUIDO_PARCIAL.label,
            ),
        ),
    )
    referencia_externa = forms.CharField(label="Referência externa", max_length=100, required=False)
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
    )
    observacoes = forms.CharField(
        label="Observações da decisão",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura,
            corrente=True,
        ).select_related("documento__tipo_documento")


class FormularioRegularizacaoFinanceira(FormularioConclusaoEncerramento):
    resultado_final = None
    regularizacao_confirmada = forms.BooleanField(
        label="Confirmo que não existem movimentos financeiros pendentes."
    )
    sem_pagamento = forms.BooleanField(
        label="O encerramento não implica pagamento",
        required=False,
    )
    motivo = forms.CharField(
        label="Justificação da decisão sem pagamento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    observacoes = None


class FormularioCorrecao(FormularioConfirmacaoWorkflow):
    motivo = forms.CharField(
        label="Motivo da correção administrativa",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
