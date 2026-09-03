import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura
from apps.documentos.models import VersaoDocumento
from apps.organizacoes.models import VinculoLaboral

from .models import ApoioFinanceiro, MovimentoFinanceiro, Restituicao


class FormularioFinanceiroBase(forms.Form):
    chave_idempotencia = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidatura = candidatura
        self.fields["chave_idempotencia"].initial = uuid.uuid4().hex


class FormularioCalculo(forms.Form):
    usar_valores_finais = forms.BooleanField(
        label="Usar horas frequentadas e custos pagos",
        required=False,
        help_text="Ative apenas quando a execução da formação já estiver registada.",
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidatura = candidatura
        participations = candidatura.beneficiarios.prefetch_related("participacoes_formacao")
        for beneficiary in participations:
            unemployed = beneficiary.situacao_referencia == VinculoLaboral.Situacao.DESEMPREGADO
            for participation in beneficiary.participacoes_formacao.all():
                suffix = str(participation.pk)
                label = f"{beneficiary.candidato} — {participation.acao_formacao}"
                self.fields[f"terceiros_{suffix}"] = forms.DecimalField(
                    label=f"Financiamento de terceiros — {label}",
                    min_value=0,
                    decimal_places=2,
                    required=False,
                    initial=0,
                )
                if unemployed:
                    self.fields[f"bolsa_{suffix}"] = forms.BooleanField(
                        label=f"Pediu bolsa e a formadora não a atribuiu — {label}",
                        required=False,
                    )
                    self.fields[f"refeicao_{suffix}"] = forms.BooleanField(
                        label=(
                            f"Pediu subsídio de refeição e a formadora não o atribuiu — {label}"
                        ),
                        required=False,
                    )
                    self.fields[f"transporte_{suffix}"] = forms.DecimalField(
                        label=f"Transporte coletivo comprovado — {label}",
                        min_value=0,
                        decimal_places=2,
                        required=False,
                    )

    def opcoes(self):
        third_party = {}
        social = {}
        for beneficiary in self.candidatura.beneficiarios.prefetch_related(
            "participacoes_formacao"
        ):
            for participation in beneficiary.participacoes_formacao.all():
                suffix = str(participation.pk)
                third_party[participation.pk] = self.cleaned_data.get(f"terceiros_{suffix}") or 0
                if f"bolsa_{suffix}" in self.fields:
                    social[participation.pk] = {
                        "bolsa": self.cleaned_data.get(f"bolsa_{suffix}", False),
                        "refeicao": self.cleaned_data.get(f"refeicao_{suffix}", False),
                    }
                    transport = self.cleaned_data.get(f"transporte_{suffix}")
                    if transport is not None:
                        social[participation.pk]["transporte"] = transport
        return third_party, social


class FormularioConfirmacaoOficial(forms.Form):
    apoio = forms.ModelChoiceField(label="Linha de apoio", queryset=ApoioFinanceiro.objects.none())
    valor_aprovado = forms.DecimalField(label="Valor aprovado", min_value=0, decimal_places=2)
    valor_final = forms.DecimalField(
        label="Valor final",
        min_value=0,
        decimal_places=2,
        required=False,
        help_text="Obrigatório para concluir o encerramento.",
    )
    confirmado_em = forms.DateTimeField(
        label="Confirmado em",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    referencia_externa = forms.CharField(label="Referência oficial", max_length=100, required=False)
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
    )

    def __init__(self, *args, candidatura, apoios, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["apoio"].queryset = apoios
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura, corrente=True
        )
        current = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["confirmado_em"].initial = current.strftime("%Y-%m-%dT%H:%M:%S")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("referencia_externa", "").strip() and not cleaned.get("evidencia"):
            raise ValidationError("Associe uma referência ou uma evidência oficial.")
        return cleaned


class FormularioMovimento(FormularioFinanceiroBase):
    apoio = forms.ModelChoiceField(label="Linha de apoio", queryset=ApoioFinanceiro.objects.none())
    tipo = forms.ChoiceField(label="Tipo", choices=MovimentoFinanceiro.Tipo.choices)
    direcao = forms.ChoiceField(label="Direção", choices=MovimentoFinanceiro.Direcao.choices)
    valor = forms.DecimalField(label="Valor", min_value=0.01, decimal_places=2)
    estado = forms.ChoiceField(
        label="Estado",
        choices=(
            (MovimentoFinanceiro.Estado.PREVISTO, "Previsto"),
            (MovimentoFinanceiro.Estado.CONFIRMADO, "Confirmado"),
            (MovimentoFinanceiro.Estado.FALHOU, "Falhou"),
        ),
    )
    previsto_para = forms.DateTimeField(
        label="Previsto para",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M",),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    efetivado_em = forms.DateTimeField(
        label="Efetivado em",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    referencia_externa = forms.CharField(label="Referência externa", max_length=100, required=False)
    comprovativo = forms.ModelChoiceField(
        label="Comprovativo", queryset=VersaoDocumento.objects.none(), required=False
    )

    def __init__(self, *args, candidatura, apoios, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        self.fields["apoio"].queryset = apoios
        self.fields["comprovativo"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura, corrente=True
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("estado") == MovimentoFinanceiro.Estado.CONFIRMADO:
            if not cleaned.get("efetivado_em"):
                self.add_error("efetivado_em", "Indique quando o movimento foi efetivado.")
            if not cleaned.get("referencia_externa", "").strip() and not cleaned.get(
                "comprovativo"
            ):
                raise ValidationError("Um movimento confirmado exige referência ou comprovativo.")
        return cleaned


class FormularioRisco(FormularioFinanceiroBase):
    motivo = forms.CharField(label="Indício identificado", widget=forms.Textarea(attrs={"rows": 3}))


class FormularioRestituicao(FormularioFinanceiroBase):
    beneficiario = forms.ModelChoiceField(
        label="Beneficiário específico",
        queryset=BeneficiarioCandidatura.objects.none(),
        required=False,
        help_text="Deixe vazio quando a decisão se aplica a toda a candidatura.",
    )
    notificada_em = forms.DateTimeField(
        label="Notificada em",
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    valor = forms.DecimalField(label="Valor a restituir", min_value=0.01, decimal_places=2)
    motivo = forms.CharField(label="Motivo comunicado", widget=forms.Textarea(attrs={"rows": 3}))
    referencia_externa = forms.CharField(label="Referência oficial", max_length=100, required=False)
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
    )

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, candidatura=candidatura, **kwargs)
        self.fields["beneficiario"].queryset = candidatura.beneficiarios.select_related(
            "candidato__utilizador"
        )
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura, corrente=True
        )
        current = timezone.localtime(timezone.now()).replace(microsecond=0)
        self.fields["notificada_em"].initial = current.strftime("%Y-%m-%dT%H:%M:%S")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("referencia_externa", "").strip() and not cleaned.get("evidencia"):
            raise ValidationError("Associe a comunicação oficial da restituição.")
        return cleaned


class FormularioRegularizacaoRestituicao(forms.Form):
    restituicao = forms.ModelChoiceField(label="Restituição", queryset=Restituicao.objects.none())
    valor_restituido = forms.DecimalField(
        label="Total já restituído", min_value=0, decimal_places=2
    )
    dispensada = forms.BooleanField(
        label="A restituição foi oficialmente dispensada", required=False
    )
    regularizada_em = forms.DateTimeField(
        label="Regularizada em",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "step": 1}),
    )
    referencia_externa = forms.CharField(
        label="Referência da regularização", max_length=100, required=False
    )
    evidencia = forms.ModelChoiceField(
        label="Evidência documental",
        queryset=VersaoDocumento.objects.none(),
        required=False,
    )

    def __init__(self, *args, candidatura, restituicoes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["restituicao"].queryset = restituicoes
        self.fields["evidencia"].queryset = VersaoDocumento.objects.filter(
            documento__candidatura=candidatura, corrente=True
        )

    def clean(self):
        cleaned = super().clean()
        refund = cleaned.get("restituicao")
        paid = cleaned.get("valor_restituido")
        final = bool(refund and (cleaned.get("dispensada") or paid == refund.valor))
        if final and not cleaned.get("regularizada_em"):
            self.add_error("regularizada_em", "Indique a data da regularização final.")
        return cleaned
