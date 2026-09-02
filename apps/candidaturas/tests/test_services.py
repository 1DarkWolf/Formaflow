from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.candidaturas.exceptions import ConflitoVersao
from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura, ParticipacaoFormacao
from apps.candidaturas.services import (
    adicionar_beneficiario,
    associar_participacao,
    criar_candidatura_empresarial,
    criar_candidatura_individual,
    definir_conta_pagamento,
    executar_verificacoes_basicas,
)
from apps.contas.models import PerfilCandidato, Utilizador
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import AssociacaoEmpresa, Empresa, EntidadeFormadora, VinculoLaboral
from apps.organizacoes.services import criar_conta_pagamento
from apps.regras.models import ConjuntoRegras, ParametroRegra
from apps.regras.services import publicar_conjunto

PASSWORD = "Segura!2026Projeto"
VALID_IBAN = "PT50000201231234567890154"


class ApplicationServiceTests(TestCase):
    def setUp(self):
        self.administrator = Utilizador.objects.create_superuser(
            email="admin.candidaturas@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Candidaturas",
        )
        self.manager = Utilizador.objects.create_user(
            email="gestor.candidaturas@example.test",
            password=PASSWORD,
            nome_proprio="Gestor",
            apelido="Empresa",
        )
        self.company = Empresa.objects.create(
            nipc="100000010",
            denominacao_legal="Empresa Candidaturas, Lda.",
        )
        self.other_company = Empresa.objects.create(
            nipc="100000029",
            denominacao_legal="Empresa Fora do Âmbito, Lda.",
        )
        AssociacaoEmpresa.objects.create(
            utilizador=self.manager,
            empresa=self.company,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            inicio_em=timezone.now() - timedelta(days=1),
        )
        self.candidates = [
            self.make_candidate("pessoa1@example.test", "100000002", "Pessoa", "Um"),
            self.make_candidate("pessoa2@example.test", "100000010", "Pessoa", "Dois"),
            self.make_candidate("pessoa3@example.test", "100000029", "Pessoa", "Três"),
        ]
        self.links = [self.make_employment(candidate) for candidate in self.candidates]
        self.rules = ConjuntoRegras.objects.create(
            codigo="CANDIDATURAS",
            versao=1,
            designacao="Regras de candidaturas",
            vigente_desde=date(2026, 1, 1),
            fonte="Teste",
        )
        ParametroRegra.objects.create(
            conjunto_regras=self.rules,
            codigo="CFG-EMPRESA-BENEFICIARIOS",
            designacao="Limite empresarial",
            tipo_valor=ParametroRegra.TipoValor.INTEIRO,
            valor=2,
        )
        publicar_conjunto(self.rules.pk, self.administrator)
        self.rules.refresh_from_db()

    @staticmethod
    def make_candidate(email, nif, first_name, last_name):
        user = Utilizador.objects.create_user(
            email=email,
            password=PASSWORD,
            nome_proprio=first_name,
            apelido=last_name,
        )
        return PerfilCandidato.objects.create(
            utilizador=user,
            nif=nif,
            data_nascimento=date(1990, 1, 1),
        )

    def make_employment(self, candidate, company=None):
        return VinculoLaboral.objects.create(
            candidato=candidate,
            empresa=company or self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=timezone.localdate() - timedelta(days=30),
            nivel_qualificacao=4,
        )

    def make_action(self, name="Formação de teste"):
        provider, _ = EntidadeFormadora.objects.get_or_create(
            nipc="111111110",
            defaults={"denominacao_legal": "Formadora de Teste, Lda."},
        )
        action = AcaoFormacao.objects.create(
            entidade_formadora=provider,
            designacao=name,
            area_codigo="481",
            inicio_previsto=date(2026, 10, 1),
            fim_previsto=date(2026, 11, 1),
        )
        component = ComponenteFormacao(
            acao_formacao=action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.CNQ,
            codigo_cnq="UFCD-TESTE",
            designacao="Componente de teste",
            area_codigo="481",
            horas=Decimal("25"),
        )
        component.full_clean()
        component.save()
        return action

    def create_business_application(self):
        return criar_candidatura_empresarial(
            criada_por=self.manager,
            titular_empresa=self.company,
            conjunto_regras=self.rules,
        )

    def test_individual_application_creates_exact_holder_beneficiary(self):
        candidate = self.candidates[0]
        application = criar_candidatura_individual(
            criada_por=candidate.utilizador,
            vinculo_referencia=self.links[0],
            conjunto_regras=self.rules,
        )

        self.assertEqual(application.tipo, Candidatura.Tipo.INDIVIDUAL)
        self.assertEqual(application.titular_candidato, candidate)
        self.assertIsNone(application.titular_empresa)
        self.assertEqual(application.beneficiarios.count(), 1)
        beneficiary = application.beneficiarios.get()
        self.assertEqual(beneficiary.candidato, candidate)
        self.assertTrue(beneficiary.e_titular)
        self.assertEqual(beneficiary.nivel_qualificacao_referencia, 4)

    def test_incoherent_holder_is_rejected(self):
        application = Candidatura(
            tipo=Candidatura.Tipo.INDIVIDUAL,
            titular_candidato=self.candidates[0],
            titular_empresa=self.company,
            criada_por=self.manager,
        )

        with self.assertRaises(ValidationError):
            application.full_clean()

    def test_business_limit_accepts_exact_limit_and_rejects_next(self):
        application = self.create_business_application()
        for candidate in self.candidates[:2]:
            adicionar_beneficiario(
                candidatura_id=application.pk,
                candidato=candidate,
                utilizador=self.manager,
                versao_esperada=application.versao,
            )
            application.refresh_from_db()

        with self.assertRaises(ValidationError):
            adicionar_beneficiario(
                candidatura_id=application.pk,
                candidato=self.candidates[2],
                utilizador=self.manager,
                versao_esperada=application.versao,
            )

        self.assertEqual(application.beneficiarios.count(), 2)

    def test_duplicate_beneficiary_is_rejected_without_removing_existing(self):
        application = self.create_business_application()
        adicionar_beneficiario(
            candidatura_id=application.pk,
            candidato=self.candidates[0],
            utilizador=self.manager,
            versao_esperada=application.versao,
        )
        application.refresh_from_db()

        with self.assertRaises(ValidationError):
            adicionar_beneficiario(
                candidatura_id=application.pk,
                candidato=self.candidates[0],
                utilizador=self.manager,
                versao_esperada=application.versao,
            )

        self.assertEqual(application.beneficiarios.count(), 1)

    def test_worker_requires_current_employment_in_holder_company(self):
        outsider = self.make_candidate(
            "sem.vinculo@example.test",
            "100000037",
            "Sem",
            "Vínculo",
        )
        application = self.create_business_application()

        with self.assertRaises(ValidationError):
            adicionar_beneficiario(
                candidatura_id=application.pk,
                candidato=outsider,
                utilizador=self.manager,
                versao_esperada=application.versao,
            )

    def test_manager_cannot_create_for_company_outside_scope(self):
        with self.assertRaises(PermissionDenied):
            criar_candidatura_empresarial(
                criada_por=self.manager,
                titular_empresa=self.other_company,
                conjunto_regras=self.rules,
            )

    def test_individual_creation_requires_current_link_and_authorized_user(self):
        expired_link = VinculoLaboral.objects.create(
            candidato=self.candidates[0],
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=date(2025, 1, 1),
            fim_em=date(2025, 12, 31),
        )
        with self.assertRaises(ValidationError):
            criar_candidatura_individual(
                criada_por=self.candidates[0].utilizador,
                vinculo_referencia=expired_link,
                conjunto_regras=self.rules,
            )

        outsider = Utilizador.objects.create_user(
            email="gestor.sem.ambito@example.test",
            password=PASSWORD,
            nome_proprio="Gestor",
            apelido="Sem âmbito",
        )
        with self.assertRaises(PermissionDenied):
            criar_candidatura_individual(
                criada_por=outsider,
                vinculo_referencia=self.links[0],
                conjunto_regras=self.rules,
            )

        application = criar_candidatura_individual(
            criada_por=self.manager,
            vinculo_referencia=self.links[0],
            conjunto_regras=self.rules,
        )
        self.assertEqual(application.titular_candidato, self.candidates[0])

    def test_new_application_rejects_unpublished_rules(self):
        draft = ConjuntoRegras.objects.create(
            codigo="RASCUNHO",
            versao=1,
            designacao="Regras não publicadas",
            vigente_desde=date(2026, 1, 1),
            fonte="Teste",
        )

        with self.assertRaises(ValidationError):
            criar_candidatura_empresarial(
                criada_por=self.manager,
                titular_empresa=self.company,
                conjunto_regras=draft,
            )

    def test_inactive_candidate_cannot_be_added(self):
        application = self.create_business_application()
        self.candidates[0].utilizador.is_active = False
        self.candidates[0].utilizador.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            adicionar_beneficiario(
                candidatura_id=application.pk,
                candidato=self.candidates[0],
                utilizador=self.manager,
                versao_esperada=application.versao,
            )

    def test_optimistic_version_conflict_does_not_overwrite_account(self):
        candidate = self.candidates[0]
        application = criar_candidatura_individual(
            criada_por=candidate.utilizador,
            vinculo_referencia=self.links[0],
            conjunto_regras=self.rules,
        )
        first = criar_conta_pagamento(
            iban=VALID_IBAN,
            nome_titular="Pessoa Um",
            candidato=candidate,
        )
        second = criar_conta_pagamento(
            iban="PT50002700000001234567833",
            nome_titular="Pessoa Um",
            candidato=candidate,
        )
        stale_version = application.versao
        definir_conta_pagamento(
            candidatura_id=application.pk,
            conta_pagamento=first,
            utilizador=candidate.utilizador,
            versao_esperada=stale_version,
        )

        with self.assertRaises(ConflitoVersao):
            definir_conta_pagamento(
                candidatura_id=application.pk,
                conta_pagamento=second,
                utilizador=candidate.utilizador,
                versao_esperada=stale_version,
            )

        application.refresh_from_db()
        self.assertEqual(application.conta_pagamento, first)
        self.assertEqual(application.versao, stale_version + 1)

    def test_payment_account_must_belong_to_holder(self):
        application = self.create_business_application()
        wrong_account = criar_conta_pagamento(
            iban=VALID_IBAN,
            nome_titular="Empresa errada",
            empresa=self.other_company,
        )

        with self.assertRaises(ValidationError):
            definir_conta_pagamento(
                candidatura_id=application.pk,
                conta_pagamento=wrong_account,
                utilizador=self.manager,
                versao_esperada=application.versao,
            )

        application.refresh_from_db()
        self.assertIsNone(application.conta_pagamento)
        self.assertEqual(application.versao, 1)

    def test_participation_is_unique_and_rejects_negative_values(self):
        application = self.create_business_application()
        beneficiary = adicionar_beneficiario(
            candidatura_id=application.pk,
            candidato=self.candidates[0],
            utilizador=self.manager,
            versao_esperada=application.versao,
        )
        application.refresh_from_db()
        action = self.make_action()
        associar_participacao(
            candidatura_id=application.pk,
            beneficiario=beneficiary,
            acao_formacao=action,
            horas_previstas=Decimal("25"),
            custo_declarado=Decimal("100"),
            utilizador=self.manager,
            versao_esperada=application.versao,
        )
        application.refresh_from_db()

        with self.assertRaises(ValidationError):
            associar_participacao(
                candidatura_id=application.pk,
                beneficiario=beneficiary,
                acao_formacao=action,
                horas_previstas=Decimal("25"),
                custo_declarado=Decimal("100"),
                utilizador=self.manager,
                versao_esperada=application.versao,
            )

        invalid = ParticipacaoFormacao(
            beneficiario=beneficiary,
            acao_formacao=self.make_action("Outra formação"),
            horas_previstas=Decimal("-1"),
            custo_declarado=Decimal("-0.01"),
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_basic_eligibility_checks_explain_current_draft(self):
        application = self.create_business_application()
        beneficiary = adicionar_beneficiario(
            candidatura_id=application.pk,
            candidato=self.candidates[0],
            utilizador=self.manager,
            versao_esperada=application.versao,
        )
        application.refresh_from_db()
        action = self.make_action()
        associar_participacao(
            candidatura_id=application.pk,
            beneficiario=beneficiary,
            acao_formacao=action,
            horas_previstas=Decimal("25"),
            custo_declarado=Decimal("100"),
            utilizador=self.manager,
            versao_esperada=application.versao,
        )

        checks = executar_verificacoes_basicas(
            candidatura_id=application.pk,
            utilizador=self.manager,
        )

        self.assertEqual(checks.count(), 3)
        self.assertFalse(checks.exclude(resultado="CONFORME").exists())
        self.assertEqual(
            checks.get(codigo_regra="RN-FOR-002").valor_avaliado,
            {"tipologia": "CNQ"},
        )

    def test_individual_beneficiary_model_rejects_another_person(self):
        application = criar_candidatura_individual(
            criada_por=self.candidates[0].utilizador,
            vinculo_referencia=self.links[0],
            conjunto_regras=self.rules,
        )
        invalid = BeneficiarioCandidatura(
            candidatura=application,
            candidato=self.candidates[1],
            e_titular=True,
            situacao_referencia=VinculoLaboral.Situacao.CONTA_OUTREM,
        )

        with self.assertRaises(ValidationError):
            invalid.full_clean()
