from urllib.parse import urlparse

from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.contas.constants import GRUPO_CANDIDATO
from apps.contas.models import PerfilCandidato, TentativaAutenticacao, Utilizador
from apps.contas.tokens import token_ativacao_conta

PASSWORD = "Segura!2026Projeto"


class AuthenticationTests(TestCase):
    def setUp(self):
        self.active_user = Utilizador.objects.create_user(
            email="ativa@example.test",
            password=PASSWORD,
            nome_proprio="Ana",
            apelido="Ativa",
        )
        self.inactive_user = Utilizador.objects.create_user(
            email="inativa@example.test",
            password=PASSWORD,
            nome_proprio="Inês",
            apelido="Inativa",
            is_active=False,
        )

    def test_login_accepts_normalized_email(self):
        response = self.client.post(
            reverse("contas:login"),
            {"username": "  ATIVA@EXAMPLE.TEST ", "password": PASSWORD},
        )

        self.assertRedirects(response, reverse("contas:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.active_user.pk)

    def test_login_uses_generic_error_for_wrong_password(self):
        response = self.client.post(
            reverse("contas:login"),
            {"username": self.active_user.email, "password": "incorreta"},
        )

        self.assertEqual(response.status_code, 200)
        error = response.context["form"].errors.as_data()[NON_FIELD_ERRORS][0]
        self.assertEqual(error.code, "invalid_login")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_login(self):
        response = self.client.post(
            reverse("contas:login"),
            {"username": self.inactive_user.email, "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        error = response.context["form"].errors.as_data()[NON_FIELD_ERRORS][0]
        self.assertEqual(error.code, "invalid_login")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_repeated_failures_temporarily_block_even_the_correct_password(self):
        for _attempt in range(5):
            self.client.post(
                reverse("contas:login"),
                {"username": self.active_user.email, "password": "incorreta"},
            )

        response = self.client.post(
            reverse("contas:login"),
            {"username": self.active_user.email, "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(TentativaAutenticacao.objects.filter(bloqueado_ate__isnull=False).exists())

    def test_successful_login_clears_previous_failures(self):
        self.client.post(
            reverse("contas:login"),
            {"username": self.active_user.email, "password": "incorreta"},
        )

        self.client.post(
            reverse("contas:login"),
            {"username": self.active_user.email, "password": PASSWORD},
        )

        self.assertFalse(TentativaAutenticacao.objects.exists())

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("contas:dashboard"))

        expected = f"{reverse('contas:login')}?next={reverse('contas:dashboard')}"
        self.assertRedirects(response, expected)

    def test_logout_requires_post_and_ends_session(self):
        self.client.force_login(self.active_user)

        self.assertEqual(self.client.get(reverse("contas:logout")).status_code, 405)
        response = self.client.post(reverse("contas:logout"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_change_keeps_session_valid(self):
        self.client.force_login(self.active_user)
        response = self.client.post(
            reverse("contas:password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": "AindaMaisSegura!2027",
                "new_password2": "AindaMaisSegura!2027",
            },
        )

        self.assertRedirects(response, reverse("contas:password_change_done"))
        self.assertIn("_auth_user_id", self.client.session)
        self.active_user.refresh_from_db()
        self.assertTrue(self.active_user.check_password("AindaMaisSegura!2027"))


class RegistrationAndActivationTests(TestCase):
    def registration_data(self, **overrides):
        data = {
            "email": "Nova.Candidata@EXAMPLE.TEST",
            "nome_proprio": "Marta",
            "apelido": "Lopes",
            "nif": "123 456 789",
            "data_nascimento": "2000-05-20",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_registration_creates_inactive_candidate_and_sends_activation(self):
        response = self.client.post(reverse("contas:registar"), self.registration_data())

        self.assertRedirects(response, reverse("contas:registo_concluido"))
        user = Utilizador.objects.get(email="nova.candidata@example.test")
        self.assertFalse(user.is_active)
        self.assertEqual(user.perfil_candidato.nif, "123456789")
        self.assertTrue(user.groups.filter(name=GRUPO_CANDIDATO).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/conta/ativar/", mail.outbox[0].body)

    def test_activation_enables_login_and_link_cannot_be_reused(self):
        self.client.post(reverse("contas:registar"), self.registration_data())
        activation_url = next(
            line for line in mail.outbox[0].body.splitlines() if "/conta/ativar/" in line
        )
        activation_path = urlparse(activation_url).path

        response = self.client.get(activation_path)

        self.assertRedirects(response, reverse("contas:login"))
        user = Utilizador.objects.get(email="nova.candidata@example.test")
        self.assertTrue(user.is_active)
        self.assertEqual(self.client.get(activation_path).status_code, 400)
        login_response = self.client.post(
            reverse("contas:login"),
            {"username": user.email, "password": PASSWORD},
        )
        self.assertRedirects(login_response, reverse("contas:dashboard"))

    def test_invalid_activation_link_is_rejected(self):
        response = self.client.get(
            reverse("contas:ativar", kwargs={"uidb64": "invalid", "token": "invalid"})
        )

        self.assertEqual(response.status_code, 400)

    def test_registration_validates_nif_and_duplicate_email(self):
        Utilizador.objects.create_user(
            email="nova.candidata@example.test",
            password=PASSWORD,
            nome_proprio="Já",
            apelido="Existe",
        )
        response = self.client.post(
            reverse("contas:registar"),
            self.registration_data(nif="123456780"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "email", "Já existe uma conta associada a este email."
        )
        self.assertFormError(response.context["form"], "nif", "Introduza um NIF válido.")
        self.assertEqual(PerfilCandidato.objects.count(), 0)

    def test_authenticated_user_does_not_reopen_registration(self):
        user = Utilizador.objects.create_user(
            email="autenticada@example.test",
            password=PASSWORD,
            nome_proprio="Alice",
            apelido="Autenticada",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("contas:registar"))

        self.assertRedirects(response, reverse("contas:dashboard"))


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        self.user = Utilizador.objects.create_user(
            email="recuperar@example.test",
            password=PASSWORD,
            nome_proprio="Rui",
            apelido="Recuperação",
        )

    def test_existing_and_unknown_email_have_equivalent_public_response(self):
        existing = self.client.post(
            reverse("contas:password_reset"),
            {"email": self.user.email},
        )
        unknown = self.client.post(
            reverse("contas:password_reset"),
            {"email": "desconhecido@example.test"},
        )

        self.assertEqual(existing.status_code, unknown.status_code)
        self.assertEqual(existing.url, unknown.url)
        self.assertEqual(existing.url, reverse("contas:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_account_does_not_receive_recovery_email(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active", "atualizado_em"])

        response = self.client.post(
            reverse("contas:password_reset"),
            {"email": self.user.email},
        )

        self.assertRedirects(response, reverse("contas:password_reset_done"))
        self.assertEqual(mail.outbox, [])

    def test_reset_token_is_invalid_after_password_change(self):
        self.client.post(reverse("contas:password_reset"), {"email": self.user.email})
        reset_url = next(
            line for line in mail.outbox[0].body.splitlines() if "/conta/repor/" in line
        )
        original_path = urlparse(reset_url).path
        confirmation = self.client.get(original_path)
        self.assertEqual(confirmation.status_code, 302)

        response = self.client.post(
            confirmation.url,
            {
                "new_password1": "NovaSegura!2028Projeto",
                "new_password2": "NovaSegura!2028Projeto",
            },
        )

        self.assertRedirects(response, reverse("contas:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSegura!2028Projeto"))
        self.assertContains(self.client.get(original_path), "Peça uma nova recuperação")

    def test_activation_token_changes_with_account_state(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active", "atualizado_em"])
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = token_ativacao_conta.make_token(self.user)
        activation_url = reverse("contas:ativar", kwargs={"uidb64": uid, "token": token})

        self.assertRedirects(self.client.get(activation_url), reverse("contas:login"))
        self.assertEqual(self.client.get(activation_url).status_code, 400)


class AdministrationTests(TestCase):
    def test_superuser_can_open_technical_administration(self):
        admin_user = Utilizador.objects.create_superuser(
            email="admin@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Teste",
        )
        Group.objects.get(name="Administrador")
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_superuser_dashboard_displays_administrator_role_without_group(self):
        admin_user = Utilizador.objects.create_superuser(
            email="painel.admin@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Painel",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("contas:dashboard"))

        self.assertContains(response, "Administrador")
