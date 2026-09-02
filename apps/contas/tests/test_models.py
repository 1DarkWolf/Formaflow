from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.contas.constants import GRUPOS_INICIAIS
from apps.contas.models import PerfilCandidato, Utilizador
from apps.contas.validators import validar_nif


class UtilizadorTests(TestCase):
    def test_manager_requires_email(self):
        with self.assertRaises(ValueError):
            Utilizador.objects.create_user(
                email="",
                password="Segura!2026Projeto",
                nome_proprio="Sem",
                apelido="Email",
            )

    def test_manager_normalizes_complete_email(self):
        user = Utilizador.objects.create_user(
            email="  Candidato@EXAMPLE.TEST ",
            password="Segura!2026Projeto",
            nome_proprio="Ana",
            apelido="Silva",
        )

        self.assertEqual(user.email, "candidato@example.test")
        self.assertEqual(user.get_full_name(), "Ana Silva")
        self.assertEqual(user.get_short_name(), "Ana")
        self.assertEqual(str(user), "candidato@example.test")

    def test_case_insensitive_email_constraint_prevents_duplicate(self):
        Utilizador.objects.create_user(
            email="pessoa@example.test",
            password="Segura!2026Projeto",
            nome_proprio="Ana",
            apelido="Silva",
        )

        with self.assertRaises(ValidationError):
            Utilizador.objects.create_user(
                email="PESSOA@EXAMPLE.TEST",
                password="Segura!2026Projeto",
                nome_proprio="Outra",
                apelido="Pessoa",
            )

        duplicate = Utilizador(
            email="PESSOA@EXAMPLE.TEST",
            nome_proprio="Outra",
            apelido="Pessoa",
        )
        duplicate.set_password("Segura!2026Projeto")
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_superuser_has_required_technical_flags(self):
        user = Utilizador.objects.create_superuser(
            email="admin@example.test",
            password="Segura!2026Projeto",
            nome_proprio="Admin",
            apelido="Forma Flow",
        )

        self.assertTrue(user.is_active)
        self.assertTrue(user.equipa_interna)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_superuser_rejects_incompatible_flags(self):
        invalid_flags = ("is_active", "is_staff", "is_superuser")

        for flag in invalid_flags:
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                Utilizador.objects.create_superuser(
                    email=f"{flag}@example.test",
                    password="Segura!2026Projeto",
                    nome_proprio="Admin",
                    apelido="Inválido",
                    **{flag: False},
                )

    def test_initial_roles_exist(self):
        self.assertCountEqual(
            Group.objects.filter(name__in=GRUPOS_INICIAIS).values_list("name", flat=True),
            GRUPOS_INICIAIS,
        )


class PerfilCandidatoTests(TestCase):
    def setUp(self):
        self.user = Utilizador.objects.create_user(
            email="candidato@example.test",
            password="Segura!2026Projeto",
            nome_proprio="Rita",
            apelido="Costa",
        )

    def test_profile_normalizes_personal_identifiers(self):
        perfil = PerfilCandidato(
            utilizador=self.user,
            nif="123 456 789",
            data_nascimento=timezone.localdate() - timedelta(days=10_000),
            telefone="  +351 912 345 678 ",
            nacionalidade="pt",
            pais="pt",
        )
        perfil.full_clean()
        perfil.save()

        self.assertEqual(perfil.nif, "123456789")
        self.assertEqual(perfil.telefone, "+351 912 345 678")
        self.assertEqual(perfil.nacionalidade, "PT")
        self.assertEqual(perfil.pais, "PT")
        self.assertEqual(str(perfil), "Rita Costa")

    def test_profile_rejects_invalid_nif(self):
        perfil = PerfilCandidato(
            utilizador=self.user,
            nif="123456780",
            data_nascimento=timezone.localdate() - timedelta(days=10_000),
        )

        with self.assertRaises(ValidationError):
            perfil.full_clean()

    def test_nif_rejects_wrong_length_and_accepts_zero_check_digit(self):
        with self.assertRaises(ValidationError):
            validar_nif("123")

        validar_nif("111111110")

    def test_profile_rejects_future_birth_date(self):
        perfil = PerfilCandidato(
            utilizador=self.user,
            nif="123456789",
            data_nascimento=timezone.localdate() + timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            perfil.full_clean()
