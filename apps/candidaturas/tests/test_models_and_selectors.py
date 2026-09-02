from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.candidaturas.models import (
    AtribuicaoCandidatura,
    BeneficiarioCandidatura,
    Candidatura,
    ParticipacaoFormacao,
    VerificacaoElegibilidade,
)
from apps.candidaturas.selectors import (
    beneficiarios_visiveis_por,
    candidaturas_visiveis_por,
    utilizador_pode_editar_candidatura,
)
from apps.contas.models import PerfilCandidato, Utilizador
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import Empresa, EntidadeFormadora, VinculoLaboral

PASSWORD = "Segura!2026Projeto"


class ApplicationModelsAndSelectorsTests(TestCase):
    def setUp(self):
        self.author = self.make_user("autor@example.test", "Autor", "Teste")
        self.candidate = self.make_candidate(
            "candidato.modelo@example.test",
            "100000002",
            "Candidato",
            "Modelo",
        )
        self.other_candidate = self.make_candidate(
            "outro.modelo@example.test",
            "100000010",
            "Outro",
            "Candidato",
        )
        self.company = Empresa.objects.create(
            nipc="100000010",
            denominacao_legal="Empresa Modelo, Lda.",
        )
        self.other_company = Empresa.objects.create(
            nipc="100000029",
            denominacao_legal="Outra Empresa, Lda.",
        )
        self.link = VinculoLaboral.objects.create(
            candidato=self.candidate,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=date(2026, 1, 1),
        )
        self.other_link = VinculoLaboral.objects.create(
            candidato=self.other_candidate,
            empresa=self.other_company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=date(2026, 1, 1),
        )
        self.application = Candidatura.objects.create(
            tipo=Candidatura.Tipo.EMPRESARIAL,
            titular_empresa=self.company,
            criada_por=self.author,
        )
        self.beneficiary = BeneficiarioCandidatura.objects.create(
            candidatura=self.application,
            candidato=self.candidate,
            situacao_referencia=VinculoLaboral.Situacao.CONTA_OUTREM,
            vinculo_referencia=self.link,
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
        return PerfilCandidato.objects.create(
            utilizador=self.make_user(email, first_name, last_name),
            nif=nif,
            data_nascimento=date(1990, 1, 1),
        )

    def make_action(self):
        provider = EntidadeFormadora.objects.create(
            nipc="111111110",
            denominacao_legal="Formadora Modelo, Lda.",
        )
        action = AcaoFormacao.objects.create(
            entidade_formadora=provider,
            designacao="Ação Modelo",
            area_codigo="481",
            inicio_previsto=date(2026, 10, 1),
            fim_previsto=date(2026, 11, 1),
        )
        component = ComponenteFormacao(
            acao_formacao=action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.CNQ,
            codigo_cnq="UFCD-MODELO",
            designacao="Componente Modelo",
            area_codigo="481",
            horas=Decimal("10"),
        )
        component.full_clean()
        component.save()
        return action

    def test_read_assignment_exposes_team_scope_without_edit_permission(self):
        reader = self.make_user("leitor@example.test", "Leitor", "Processo")
        AtribuicaoCandidatura.objects.create(
            candidatura=self.application,
            utilizador=reader,
            papel=AtribuicaoCandidatura.Papel.LEITURA,
            inicio_em=timezone.now() - timedelta(days=1),
        )

        self.assertQuerySetEqual(candidaturas_visiveis_por(reader), [self.application])
        self.assertQuerySetEqual(
            beneficiarios_visiveis_por(reader, self.application),
            [self.beneficiary],
        )
        self.assertFalse(utilizador_pode_editar_candidatura(reader, self.application))

    def test_administrator_has_global_scope_and_inactive_user_has_none(self):
        administrator = Utilizador.objects.create_superuser(
            email="admin.modelo@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Modelo",
        )
        self.assertQuerySetEqual(candidaturas_visiveis_por(administrator), [self.application])
        self.assertTrue(utilizador_pode_editar_candidatura(administrator, self.application))

        self.author.is_active = False
        self.author.save(update_fields=["is_active"])
        self.assertFalse(candidaturas_visiveis_por(self.author).exists())
        self.assertFalse(utilizador_pode_editar_candidatura(self.author, self.application))

    def test_assignment_period_and_string_are_validated(self):
        assignment = AtribuicaoCandidatura(
            candidatura=self.application,
            utilizador=self.author,
            papel=AtribuicaoCandidatura.Papel.RESPONSAVEL,
            inicio_em=timezone.now(),
            fim_em=timezone.now() - timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

        assignment.fim_em = None
        assignment.full_clean()
        self.assertIn("Responsável", str(assignment))

    def test_database_rejects_incoherent_application_holder(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Candidatura.objects.create(
                tipo=Candidatura.Tipo.INDIVIDUAL,
                titular_candidato=self.candidate,
                titular_empresa=self.company,
                criada_por=self.author,
            )

    def test_beneficiary_rejects_holder_and_reference_inconsistencies(self):
        invalid = BeneficiarioCandidatura(
            candidatura=self.application,
            candidato=self.other_candidate,
            e_titular=True,
            situacao_referencia=VinculoLaboral.Situacao.CONTA_OUTREM,
            vinculo_referencia=self.link,
            resultado=BeneficiarioCandidatura.Resultado.INDEFERIDA,
        )

        with self.assertRaises(ValidationError) as error:
            invalid.full_clean()

        self.assertIn("e_titular", error.exception.message_dict)
        self.assertIn("vinculo_referencia", error.exception.message_dict)
        self.assertIn("motivo_decisao", error.exception.message_dict)
        self.assertIn("Candidato Modelo", str(self.beneficiary))

    def test_participation_rejects_limits_and_negative_values(self):
        participation = ParticipacaoFormacao(
            beneficiario=self.beneficiary,
            acao_formacao=self.make_action(),
            horas_previstas=Decimal("11"),
            horas_frequentadas=Decimal("-1"),
            custo_declarado=Decimal("-1"),
            custo_pago_formadora=Decimal("-1"),
        )

        with self.assertRaises(ValidationError) as error:
            participation.full_clean()

        self.assertIn("horas_previstas", error.exception.message_dict)
        self.assertIn("horas_frequentadas", error.exception.message_dict)
        self.assertIn("custo_declarado", error.exception.message_dict)
        self.assertIn("custo_pago_formadora", error.exception.message_dict)

        participation.horas_previstas = Decimal("10")
        participation.horas_frequentadas = None
        participation.custo_declarado = Decimal("0")
        participation.custo_pago_formadora = None
        participation.full_clean()
        self.assertIn("Ação Modelo", str(participation))

    def test_verification_normalizes_code_and_rejects_cross_scope_relations(self):
        other_application = Candidatura.objects.create(
            tipo=Candidatura.Tipo.EMPRESARIAL,
            titular_empresa=self.other_company,
            criada_por=self.author,
        )
        other_beneficiary = BeneficiarioCandidatura.objects.create(
            candidatura=other_application,
            candidato=self.other_candidate,
            situacao_referencia=VinculoLaboral.Situacao.CONTA_OUTREM,
            vinculo_referencia=self.other_link,
        )
        participation = ParticipacaoFormacao.objects.create(
            beneficiario=self.beneficiary,
            acao_formacao=self.make_action(),
            horas_previstas=Decimal("10"),
            custo_declarado=Decimal("0"),
        )
        verification = VerificacaoElegibilidade(
            candidatura=other_application,
            beneficiario=other_beneficiary,
            participacao=participation,
            codigo_regra=" rn-for-002 ",
            tipo_avaliacao=VerificacaoElegibilidade.TipoAvaliacao.AUTOMATICA,
            resultado=VerificacaoElegibilidade.Resultado.CONFORME,
            verificada_por=self.author,
        )

        with self.assertRaises(ValidationError) as error:
            verification.full_clean()

        self.assertIn("participacao", error.exception.message_dict)
        self.assertIn("beneficiario", error.exception.message_dict)
        self.assertIn("verificada_por", error.exception.message_dict)

        verification.candidatura = self.application
        verification.beneficiario = self.beneficiary
        verification.verificada_por = None
        verification.full_clean()
        verification.save()
        self.assertEqual(verification.codigo_regra, "RN-FOR-002")
        self.assertIn("Conforme", str(verification))
