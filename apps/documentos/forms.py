from django import forms
from django.core.exceptions import ValidationError

from .models import SnapshotSubmissao, VersaoDocumento


class UploadDocumentoForm(forms.Form):
    ficheiro = forms.FileField(
        label="Ficheiro PDF",
        help_text="Apenas PDF, até ao limite definido nas regras da candidatura.",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,.pdf"}),
    )
    titulo = forms.CharField(label="Título", max_length=255, required=False)
    emitido_em = forms.DateField(
        label="Data de emissão",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    valido_ate = forms.DateField(
        label="Válido até",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned = super().clean()
        emitted = cleaned.get("emitido_em")
        valid_until = cleaned.get("valido_ate")
        if emitted and valid_until and valid_until < emitted:
            self.add_error("valido_ate", "A validade não pode anteceder a emissão.")
        return cleaned


class SubstituirDocumentoForm(UploadDocumentoForm):
    titulo = None
    motivo = forms.CharField(
        label="Motivo da substituição",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class ValidarDocumentoForm(forms.Form):
    resultado = forms.ChoiceField(
        label="Decisão",
        choices=(
            (VersaoDocumento.EstadoValidacao.VALIDO, "Válido"),
            (VersaoDocumento.EstadoValidacao.INVALIDO, "Inválido"),
        ),
    )
    observacao = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("resultado") == VersaoDocumento.EstadoValidacao.INVALIDO
            and not cleaned.get("observacao", "").strip()
        ):
            self.add_error("observacao", "Explique por que motivo o documento é inválido.")
        return cleaned


class DispensarRequisitoForm(forms.Form):
    motivo = forms.CharField(
        label="Justificação da dispensa",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class SnapshotForm(forms.Form):
    finalidade = forms.ChoiceField(
        label="Finalidade",
        choices=SnapshotSubmissao.Finalidade.choices,
        initial=SnapshotSubmissao.Finalidade.SUBMISSAO,
    )

    def clean_finalidade(self):
        value = self.cleaned_data["finalidade"]
        if value not in SnapshotSubmissao.Finalidade.values:
            raise ValidationError("Escolha uma finalidade válida.")
        return value
