from django import forms

from .models import ContaPagamento
from .security import validar_iban


class ContaPagamentoAdminForm(forms.ModelForm):
    iban = forms.CharField(
        label="IBAN",
        required=False,
        help_text=(
            "Introduza apenas para criar ou substituir a conta. O valor não volta a ser mostrado."
        ),
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    class Meta:
        model = ContaPagamento
        fields = (
            "candidato",
            "empresa",
            "iban",
            "nome_titular",
            "principal",
            "ativa",
            "validada_em",
            "validada_por",
        )

    def clean_iban(self):
        iban = self.cleaned_data.get("iban", "")
        if self.instance._state.adding and not iban:
            raise forms.ValidationError("O IBAN é obrigatório ao criar a conta.")
        if iban:
            return validar_iban(iban)
        return iban

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("iban"):
            instance.definir_iban(self.cleaned_data["iban"])
        if commit:
            instance.full_clean()
            instance.save()
            self.save_m2m()
        return instance
