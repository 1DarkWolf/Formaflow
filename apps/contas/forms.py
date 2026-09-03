from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from .constants import GRUPO_CANDIDATO
from .login_security import (
    autenticacao_bloqueada,
    limpar_falhas_autenticacao,
    registar_falha_autenticacao,
)
from .models import PerfilCandidato, Utilizador
from .validators import normalizar_nif, validar_nif


class FormularioAutenticacao(AuthenticationForm):
    error_messages = {
        "invalid_login": "Introduza um email e uma palavra-passe corretos.",
        "inactive": "Introduza um email e uma palavra-passe corretos.",
    }
    username = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        ),
    )

    def clean(self):
        identifier = self.data.get("username", "")
        if autenticacao_bloqueada(request=self.request, identifier=identifier):
            raise self.get_invalid_login_error()
        try:
            cleaned_data = super().clean()
        except ValidationError:
            if identifier and self.data.get("password"):
                registar_falha_autenticacao(request=self.request, identifier=identifier)
            raise
        limpar_falhas_autenticacao(request=self.request, identifier=identifier)
        return cleaned_data


class FormularioRegistoCandidato(UserCreationForm):
    nif = forms.CharField(label="NIF", max_length=20)
    data_nascimento = forms.DateField(
        label="Data de nascimento",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
    )

    class Meta(UserCreationForm.Meta):
        model = Utilizador
        fields = ("email", "nome_proprio", "apelido")
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "autocomplete": "email",
                    "autocapitalize": "none",
                    "spellcheck": "false",
                }
            ),
            "nome_proprio": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "apelido": forms.TextInput(attrs={"autocomplete": "family-name"}),
        }

    field_order = (
        "email",
        "nome_proprio",
        "apelido",
        "nif",
        "data_nascimento",
        "password1",
        "password2",
    )

    def clean_email(self):
        email = Utilizador.objects.normalizar_email(self.cleaned_data["email"])
        if Utilizador.objects.filter(email__iexact=email).exists():
            raise ValidationError("Já existe uma conta associada a este email.")
        return email

    def clean_nif(self):
        nif = normalizar_nif(self.cleaned_data["nif"])
        validar_nif(nif)
        if PerfilCandidato.objects.filter(nif=nif).exists():
            raise ValidationError("Já existe um perfil associado a este NIF.")
        return nif

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False
        if not commit:
            return user

        user.save()
        perfil = PerfilCandidato(
            utilizador=user,
            nif=self.cleaned_data["nif"],
            data_nascimento=self.cleaned_data["data_nascimento"],
        )
        perfil.full_clean()
        perfil.save()
        grupo, _ = Group.objects.get_or_create(name=GRUPO_CANDIDATO)
        user.groups.add(grupo)
        return user


class FormularioCriacaoUtilizador(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Utilizador
        fields = ("email", "nome_proprio", "apelido")

    def clean_email(self):
        return Utilizador.objects.normalizar_email(self.cleaned_data["email"])


class FormularioAlteracaoUtilizador(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Utilizador
        fields = "__all__"

    def clean_email(self):
        return Utilizador.objects.normalizar_email(self.cleaned_data["email"])
