from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.candidaturas.models import Candidatura, ParticipacaoFormacao
from apps.candidaturas.services import (
    adicionar_beneficiario,
    criar_candidatura_empresarial,
)
from apps.contas.models import PerfilCandidato, Utilizador
from apps.formacoes.models import AcaoFormacao
from apps.organizacoes.models import (
    AssociacaoEmpresa,
    Empresa,
    EntidadeFormadora,
    VinculoLaboral,
)
from apps.organizacoes.services import criar_conta_pagamento
from apps.regras.models import ConjuntoRegras, ParametroRegra
from apps.regras.services import publicar_conjunto

PASSWORD = "Segura!2026Projeto"


class ApplicationPermissionAndViewTests(TestCase):
    def setUp(self):
        self.administrator = Utilizador.objects.create_superuser(
            email="admin.views@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Views",
        )
        self.manager_a = self.make_user("gestor.a@example.test", "Gestor", "A")
        self.manager_b = self.make_user("gestor.b@example.test", "Gestor", "B")
        self.outsider = self.make_user("sem.ambito@example.test", "Sem", "Âmbito")
        self.company_a = Empresa.objects.create(
            nipc="100000010",
            denominacao_legal="Empresa A, Lda.",
        )
        self.company_b = Empresa.objects.create(
            nipc="100000029",
            denominacao_legal="Empresa B, Lda.",
        )
        self.associate(self.manager_a, self.company_a)
        self.associate(self.manager_b, self.company_b)
        self.candidate_a = self.make_candidate(
            "candidato.a@example.test",
            "100000002",
            "Candidato",
            "Visível",
        )
        self.candidate_b = self.make_candidate(
            "candidato.b@example.test",
            "100000010",
            "Colega",
            "Privado",
        )
        self.link_a = self.employ(self.candidate_a, self.company_a)
        self.employ(self.candidate_b, self.company_a)
        self.rules = ConjuntoRegras.objects.create(
            codigo="VIEWS",
            versao=1,
            designacao="Regras para vistas",
            vigente_desde=date(2026, 1, 1),
            fonte="Teste",
        )
        ParametroRegra.objects.create(
            conjunto_regras=self.rules,
            codigo="CFG-EMPRESA-BENEFICIARIOS",
            designacao="Limite",
            tipo_valor=ParametroRegra.TipoValor.INTEIRO,
            valor=20,
        )
        publicar_conjunto(self.rules.pk, self.administrator)
        self.rules.refresh_from_db()
        self.application_a = criar_candidatura_empresarial(
            criada_por=self.manager_a,
            titular_empresa=self.company_a,
            conjunto_regras=self.rules,
        )
        for candidate in (self.candidate_a, self.candidate_b):
            adicionar_beneficiario(
                candidatura_id=self.application_a.pk,
                candidato=candidate,
                utilizador=self.manager_a,
                versao_esperada=self.application_a.versao,
            )
            self.application_a.refresh_from_db()
        self.application_b = criar_candidatura_empresarial(
            criada_por=self.manager_b,
            titular_empresa=self.company_b,
            conjunto_regras=self.rules,
        )

    @staticmethod
    def make_user(email, first_name, last_name):
        return Utilizador.objects.create_user(
            email=email,
            password=PASSWORD,
            nome_proprio=first_name,
            apelido=last_name,
        )

    def make_candidate(self, email, nif, first_name, last_name):
        user = self.make_user(email, first_name, last_name)
        return PerfilCandidato.objects.create(
            utilizador=user,
            nif=nif,
            data_nascimento=date(1992, 4, 2),
        )

    @staticmethod
    def associate(user, company):
        return AssociacaoEmpresa.objects.create(
            utilizador=user,
            empresa=company,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            inicio_em=timezone.now() - timedelta(days=1),
        )

    @staticmethod
    def employ(candidate, company):
        return VinculoLaboral.objects.create(
            candidato=candidate,
            empresa=company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=timezone.localdate() - timedelta(days=30),
        )

    def test_manager_list_is_limited_to_company_scope(self):
        self.client.force_login(self.manager_a)

        response = self.client.get(reverse("candidaturas:lista"))

        self.assertContains(response, "Empresa A, Lda.")
        self.assertNotContains(response, "Empresa B, Lda.")

    def test_candidate_in_business_application_only_sees_personal_beneficiary(self):
        self.client.force_login(self.candidate_a.utilizador)

        response = self.client.get(
            reverse("candidaturas:detalhe", args=[self.application_a.public_id])
        )

        self.assertContains(response, "Candidato Visível")
        self.assertNotContains(response, "Colega Privado")
        self.assertNotContains(response, "Adicionar beneficiário")

    def test_unknown_scope_returns_not_found_without_revealing_application(self):
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse("candidaturas:detalhe", args=[self.application_a.public_id])
        )

        self.assertEqual(response.status_code, 404)

    def test_candidate_can_create_own_individual_draft_through_wizard(self):
        self.client.force_login(self.candidate_a.utilizador)

        response = self.client.post(
            reverse("candidaturas:nova"),
            data={
                "tipo": Candidatura.Tipo.INDIVIDUAL,
                "vinculo": self.link_a.pk,
                "empresa": "",
                "conjunto_regras": self.rules.pk,
            },
        )

        application = Candidatura.objects.get(tipo=Candidatura.Tipo.INDIVIDUAL)
        self.assertRedirects(
            response,
            reverse("candidaturas:detalhe", args=[application.public_id]),
        )
        self.assertEqual(application.beneficiarios.count(), 1)

    def test_manager_can_create_business_draft_through_wizard(self):
        self.client.force_login(self.manager_a)

        response = self.client.post(
            reverse("candidaturas:nova"),
            data={
                "tipo": Candidatura.Tipo.EMPRESARIAL,
                "vinculo": "",
                "empresa": self.company_a.pk,
                "conjunto_regras": self.rules.pk,
            },
        )

        application = Candidatura.objects.filter(
            tipo=Candidatura.Tipo.EMPRESARIAL,
            titular_empresa=self.company_a,
        ).latest("pk")
        self.assertRedirects(
            response,
            reverse("candidaturas:detalhe", args=[application.public_id]),
        )

    def test_wizard_adds_training_payment_account_and_runs_checks(self):
        provider = EntidadeFormadora.objects.create(
            nipc="111111110",
            denominacao_legal="Formadora Interface, Lda.",
        )
        beneficiary = self.application_a.beneficiarios.get(candidato=self.candidate_a)
        self.client.force_login(self.manager_a)
        training_response = self.client.post(
            reverse(
                "candidaturas:adicionar_formacao",
                args=[self.application_a.public_id],
            ),
            data={
                "beneficiario": beneficiary.pk,
                "entidade_formadora": provider.pk,
                "designacao": "Desenvolvimento em Django",
                "area_codigo": "481",
                "area_designacao": "Ciências informáticas",
                "modalidade": "Mista",
                "inicio_previsto": "2026-10-01",
                "fim_previsto": "2026-11-01",
                "local": "Viseu",
                "componente_tipo": "CNQ",
                "componente_codigo_cnq": "UFCD-10791",
                "componente_designacao": "Desenvolvimento web",
                "componente_referencial": "Programador de informática",
                "componente_horas": "25",
                "justificacao_extra_cnq": "",
                "custo_declarado": "175",
                "versao": self.application_a.versao,
            },
        )

        self.assertEqual(training_response.status_code, 302)
        self.application_a.refresh_from_db()
        self.assertEqual(ParticipacaoFormacao.objects.count(), 1)
        account = criar_conta_pagamento(
            iban="PT50000201231234567890154",
            nome_titular="Empresa A, Lda.",
            empresa=self.company_a,
        )
        account_response = self.client.post(
            reverse("candidaturas:definir_conta", args=[self.application_a.public_id]),
            data={
                "conta_pagamento": account.pk,
                "versao": self.application_a.versao,
            },
        )

        self.assertEqual(account_response.status_code, 302)
        self.application_a.refresh_from_db()
        self.assertEqual(self.application_a.conta_pagamento, account)
        check_response = self.client.post(
            reverse("candidaturas:verificar", args=[self.application_a.public_id])
        )
        self.assertRedirects(
            check_response,
            reverse("candidaturas:detalhe", args=[self.application_a.public_id]),
        )
        self.assertTrue(self.application_a.verificacoes_elegibilidade.exists())

    def test_invalid_extra_cnq_form_preserves_errors_without_creating_action(self):
        provider = EntidadeFormadora.objects.create(
            nipc="111111110",
            denominacao_legal="Formadora Inválida, Lda.",
        )
        beneficiary = self.application_a.beneficiarios.get(candidato=self.candidate_a)
        self.client.force_login(self.manager_a)

        response = self.client.post(
            reverse(
                "candidaturas:adicionar_formacao",
                args=[self.application_a.public_id],
            ),
            data={
                "beneficiario": beneficiary.pk,
                "entidade_formadora": provider.pk,
                "designacao": "Formação extra",
                "area_codigo": "481",
                "area_designacao": "Informática",
                "modalidade": "Presencial",
                "inicio_previsto": "2026-10-01",
                "fim_previsto": "2026-11-01",
                "local": "Viseu",
                "componente_tipo": "EXTRA_CNQ",
                "componente_codigo_cnq": "CODIGO-INDEVIDO",
                "componente_designacao": "Conteúdo específico",
                "componente_referencial": "",
                "componente_horas": "10",
                "justificacao_extra_cnq": "",
                "custo_declarado": "100",
                "versao": self.application_a.versao,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Justifique a relevância", status_code=400)
        self.assertEqual(AcaoFormacao.objects.count(), 0)

    def test_stale_form_receives_conflict_and_preserves_previous_change(self):
        candidate_c = self.make_candidate(
            "candidato.c@example.test",
            "100000029",
            "Pessoa",
            "Nova",
        )
        self.employ(candidate_c, self.company_a)
        candidate_d = self.make_candidate(
            "candidato.d@example.test",
            "100000037",
            "Pessoa",
            "Concorrente",
        )
        self.employ(candidate_d, self.company_a)
        application = criar_candidatura_empresarial(
            criada_por=self.manager_a,
            titular_empresa=self.company_a,
            conjunto_regras=self.rules,
        )
        stale_version = application.versao
        self.client.force_login(self.manager_a)
        endpoint = reverse("candidaturas:adicionar_beneficiario", args=[application.public_id])
        first = self.client.post(
            endpoint,
            data={"candidato": candidate_c.pk, "versao": stale_version},
        )
        second = self.client.post(
            endpoint,
            data={"candidato": candidate_d.pk, "versao": stale_version},
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 409)
        self.assertContains(second, "alterada noutra sessão", status_code=409)
        self.assertTrue(application.beneficiarios.filter(candidato=candidate_c).exists())
        self.assertFalse(application.beneficiarios.filter(candidato=candidate_d).exists())

    def test_list_requires_authentication(self):
        response = self.client.get(reverse("candidaturas:lista"))

        self.assertEqual(response.status_code, 302)

    def test_technical_administration_lists_applications_and_training(self):
        self.client.force_login(self.administrator)

        applications = self.client.get(reverse("admin:candidaturas_candidatura_changelist"))
        training = self.client.get(reverse("admin:formacoes_acaoformacao_changelist"))

        self.assertEqual(applications.status_code, 200)
        self.assertEqual(training.status_code, 200)
