from django.test import TestCase

from apps.contas.forms import (
    FormularioAlteracaoUtilizador,
    FormularioCriacaoUtilizador,
    FormularioRegistoCandidato,
)
from apps.contas.models import PerfilCandidato, Utilizador

PASSWORD = "Segura!2026Projeto"


class RegistrationFormTests(TestCase):
    def form_data(self, **overrides):
        data = {
            "email": "formulario@example.test",
            "nome_proprio": "Filipa",
            "apelido": "Formulário",
            "nif": "123456789",
            "data_nascimento": "2001-04-12",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_duplicate_nif_is_rejected(self):
        existing_user = Utilizador.objects.create_user(
            email="existente@example.test",
            password=PASSWORD,
            nome_proprio="Pessoa",
            apelido="Existente",
        )
        PerfilCandidato.objects.create(
            utilizador=existing_user,
            nif="123456789",
            data_nascimento="2000-01-01",
        )
        form = FormularioRegistoCandidato(data=self.form_data())

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["nif"], ["Já existe um perfil associado a este NIF."])

    def test_save_without_commit_returns_unsaved_inactive_user(self):
        form = FormularioRegistoCandidato(data=self.form_data())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)

        self.assertIsNone(user.pk)
        self.assertFalse(user.is_active)
        self.assertFalse(Utilizador.objects.filter(email=user.email).exists())


class AdministrationFormTests(TestCase):
    def test_administration_forms_normalize_email(self):
        creation_form = FormularioCriacaoUtilizador()
        creation_form.cleaned_data = {"email": "  NOVO@EXAMPLE.TEST "}

        self.assertEqual(creation_form.clean_email(), "novo@example.test")

        change_form = FormularioAlteracaoUtilizador()
        change_form.cleaned_data = {"email": "  ALTERADO@EXAMPLE.TEST "}

        self.assertEqual(change_form.clean_email(), "alterado@example.test")
