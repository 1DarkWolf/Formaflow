from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.contas.models import PerfilCandidato, Utilizador
from apps.organizacoes.forms import ContaPagamentoAdminForm
from apps.organizacoes.models import (
    AssociacaoEmpresa,
    CertificacaoFormadora,
    ContaPagamento,
    Empresa,
    EntidadeFormadora,
    VinculoLaboral,
)
from apps.organizacoes.security import decifrar_iban, validar_iban
from apps.organizacoes.services import criar_conta_pagamento
from apps.organizacoes.validators import validar_nipc

PASSWORD = "Segura!2026Projeto"
VALID_IBAN = "PT50000201231234567890154"


class OrganizationModelTests(TestCase):
    def setUp(self):
        self.user = Utilizador.objects.create_user(
            email="pessoa@example.test",
            password=PASSWORD,
            nome_proprio="Pessoa",
            apelido="Teste",
        )
        self.profile = PerfilCandidato.objects.create(
            utilizador=self.user,
            nif="100000002",
            data_nascimento=date(1995, 5, 20),
        )
        self.company = Empresa.objects.create(
            nipc="100000010",
            denominacao_legal="Empresa Um, Lda.",
        )

    def test_company_and_provider_normalize_nipc(self):
        company = Empresa(nipc="100 000 029", denominacao_legal="Empresa Dois, Lda.")
        company.full_clean()
        company.save()
        provider = EntidadeFormadora(
            nipc="100-000-037",
            denominacao_legal="Formadora Um, Lda.",
        )
        provider.full_clean()
        provider.save()

        self.assertEqual(company.nipc, "100000029")
        self.assertEqual(provider.nipc, "100000037")
        self.assertEqual(str(company), "Empresa Dois, Lda.")
        self.assertEqual(str(provider), "Formadora Um, Lda.")

    def test_duplicate_company_nipc_is_rejected(self):
        duplicate = Empresa(nipc="100 000 010", denominacao_legal="Duplicada, Lda.")

        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_nipc_validator_rejects_length_and_check_digit(self):
        with self.assertRaises(ValidationError):
            validar_nipc("123")
        with self.assertRaises(ValidationError):
            validar_nipc("100000001")

        self.assertIsNone(validar_nipc("111 111 110"))

    def test_association_period_and_active_uniqueness(self):
        start = timezone.now()
        association = AssociacaoEmpresa.objects.create(
            utilizador=self.user,
            empresa=self.company,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            inicio_em=start,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            AssociacaoEmpresa.objects.create(
                utilizador=self.user,
                empresa=self.company,
                papel=AssociacaoEmpresa.Papel.GESTOR,
                inicio_em=start,
            )

        association.ativa = False
        association.fim_em = start + timedelta(days=1)
        association.save()
        replacement = AssociacaoEmpresa.objects.create(
            utilizador=self.user,
            empresa=self.company,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            inicio_em=start + timedelta(days=2),
        )
        self.assertIsNotNone(replacement.pk)
        self.assertIn("Gestor", str(replacement))

        replacement.fim_em = replacement.inicio_em - timedelta(seconds=1)
        with self.assertRaises(ValidationError):
            replacement.full_clean()

    def test_employment_requires_coherent_company_and_period(self):
        employment = VinculoLaboral(
            candidato=self.profile,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=date(2026, 1, 10),
            fim_em=date(2026, 1, 9),
        )

        with self.assertRaises(ValidationError) as error:
            employment.full_clean()

        self.assertIn("empresa", error.exception.message_dict)
        self.assertIn("fim_em", error.exception.message_dict)

        unemployed = VinculoLaboral(
            candidato=self.profile,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.DESEMPREGADO,
            inicio_em=date(2026, 1, 10),
        )
        with self.assertRaises(ValidationError):
            unemployed.full_clean()

        employment.empresa = self.company
        employment.fim_em = None
        employment.full_clean()
        self.assertIn("Trabalhador por conta de outrem", str(employment))

    def test_provider_certification_requires_area_and_valid_period(self):
        provider = EntidadeFormadora.objects.create(
            nipc="100000029",
            denominacao_legal="Formadora, Lda.",
        )
        certification = CertificacaoFormadora(
            entidade_formadora=provider,
            enquadramento=CertificacaoFormadora.Enquadramento.CERTIFICADA_DGERT,
            valida_desde=date(2026, 2, 1),
            valida_ate=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError) as error:
            certification.full_clean()

        self.assertIn("area_codigo", error.exception.message_dict)
        self.assertIn("valida_ate", error.exception.message_dict)

        certification.area_codigo = "090"
        certification.valida_ate = date(2027, 1, 1)
        certification.full_clean()
        self.assertIn("Certificada pela DGERT", str(certification))


class PaymentAccountTests(TestCase):
    def setUp(self):
        self.company = Empresa.objects.create(
            nipc="100000010",
            denominacao_legal="Empresa Pagamentos, Lda.",
        )

    def test_service_encrypts_hashes_and_masks_iban(self):
        account = criar_conta_pagamento(
            iban=VALID_IBAN,
            nome_titular="Empresa Pagamentos, Lda.",
            empresa=self.company,
            principal=True,
        )

        self.assertNotIn(VALID_IBAN, account.iban_cifrado)
        self.assertEqual(len(account.iban_hash), 64)
        self.assertEqual(account.iban_ultimos_4, "0154")
        self.assertEqual(account.iban_mascarado, "•••• 0154")
        self.assertEqual(decifrar_iban(account.iban_cifrado), VALID_IBAN)
        self.assertNotIn(VALID_IBAN, str(account))

    def test_invalid_iban_is_rejected(self):
        with self.assertRaises(ValidationError):
            validar_iban("PT00 INVALIDO")

    def test_account_requires_exactly_one_owner(self):
        user = Utilizador.objects.create_user(
            email="titular@example.test",
            password=PASSWORD,
            nome_proprio="Titular",
            apelido="Conta",
        )
        profile = PerfilCandidato.objects.create(
            utilizador=user,
            nif="100000002",
            data_nascimento=date(1990, 1, 1),
        )
        account = ContaPagamento(
            candidato=profile,
            empresa=self.company,
            nome_titular="Titular inválido",
        )
        account.definir_iban(VALID_IBAN)

        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_only_one_active_primary_account_per_owner(self):
        criar_conta_pagamento(
            iban=VALID_IBAN,
            nome_titular="Primeira",
            empresa=self.company,
            principal=True,
        )

        with self.assertRaises(ValidationError):
            criar_conta_pagamento(
                iban="PT50002700000001234567833",
                nome_titular="Segunda",
                empresa=self.company,
                principal=True,
            )

    def test_administration_form_never_exposes_stored_iban(self):
        account = criar_conta_pagamento(
            iban=VALID_IBAN,
            nome_titular="Empresa Pagamentos, Lda.",
            empresa=self.company,
        )
        form = ContaPagamentoAdminForm(instance=account)

        self.assertNotIn("iban_cifrado", form.fields)
        self.assertNotIn("iban_hash", form.fields)
        self.assertEqual(form.fields["iban"].initial, None)

    def test_administration_form_creates_and_updates_without_revealing_iban(self):
        form = ContaPagamentoAdminForm(
            data={
                "candidato": "",
                "empresa": self.company.pk,
                "iban": VALID_IBAN,
                "nome_titular": "Empresa Pagamentos, Lda.",
                "principal": "on",
                "ativa": "on",
                "validada_em": "",
                "validada_por": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        account = form.save()
        original_ciphertext = account.iban_cifrado

        edit_form = ContaPagamentoAdminForm(
            data={
                "candidato": "",
                "empresa": self.company.pk,
                "iban": "",
                "nome_titular": "Titular atualizado",
                "principal": "on",
                "ativa": "on",
                "validada_em": "",
                "validada_por": "",
            },
            instance=account,
        )
        self.assertTrue(edit_form.is_valid(), edit_form.errors)
        updated = edit_form.save()

        self.assertEqual(updated.iban_cifrado, original_ciphertext)
        self.assertEqual(updated.nome_titular, "Titular atualizado")

    def test_administration_form_requires_iban_on_creation(self):
        form = ContaPagamentoAdminForm(
            data={
                "candidato": "",
                "empresa": self.company.pk,
                "iban": "",
                "nome_titular": "Sem IBAN",
                "principal": "",
                "ativa": "on",
                "validada_em": "",
                "validada_por": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("iban", form.errors)
