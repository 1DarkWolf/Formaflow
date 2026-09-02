from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import EntidadeFormadora


class TrainingModelTests(TestCase):
    def setUp(self):
        self.provider = EntidadeFormadora.objects.create(
            nipc="111111110",
            denominacao_legal="Formadora de Teste, Lda.",
        )
        self.action = AcaoFormacao.objects.create(
            entidade_formadora=self.provider,
            designacao="Programação web",
            area_codigo="481",
            inicio_previsto=date(2026, 10, 1),
            fim_previsto=date(2026, 12, 1),
        )

    def test_components_derive_hours_and_mixed_typology(self):
        cnq = ComponenteFormacao(
            acao_formacao=self.action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.CNQ,
            codigo_cnq="UFCD-0001",
            designacao="Componente CNQ",
            area_codigo="481",
            horas=Decimal("25"),
        )
        cnq.full_clean()
        cnq.save()
        self.action.refresh_from_db()

        self.assertEqual(self.action.tipologia, AcaoFormacao.Tipologia.CNQ)
        self.assertEqual(self.action.horas_totais, Decimal("25"))

        extra = ComponenteFormacao(
            acao_formacao=self.action,
            ordem=2,
            tipo=ComponenteFormacao.Tipo.EXTRA_CNQ,
            designacao="Componente específica",
            area_codigo="481",
            horas=Decimal("10.5"),
            justificacao_extra_cnq="Relevante para a integração profissional.",
        )
        extra.full_clean()
        extra.save()
        self.action.refresh_from_db()

        self.assertEqual(self.action.tipologia, AcaoFormacao.Tipologia.MISTA)
        self.assertEqual(self.action.horas_totais, Decimal("35.50"))

        extra.delete()
        self.action.refresh_from_db()
        self.assertEqual(self.action.tipologia, AcaoFormacao.Tipologia.CNQ)
        self.assertEqual(self.action.horas_totais, Decimal("25"))

    def test_extra_cnq_requires_justification_and_rejects_cnq_code(self):
        component = ComponenteFormacao(
            acao_formacao=self.action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.EXTRA_CNQ,
            codigo_cnq="NAO-APLICAVEL",
            designacao="Componente externa",
            horas=Decimal("10"),
        )

        with self.assertRaises(ValidationError) as error:
            component.full_clean()

        self.assertIn("codigo_cnq", error.exception.message_dict)
        self.assertIn("justificacao_extra_cnq", error.exception.message_dict)

    def test_cnq_requires_code_and_matching_area(self):
        component = ComponenteFormacao(
            acao_formacao=self.action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.CNQ,
            designacao="Componente inconsistente",
            area_codigo="999",
            horas=Decimal("10"),
        )

        with self.assertRaises(ValidationError) as error:
            component.full_clean()

        self.assertIn("codigo_cnq", error.exception.message_dict)
        self.assertIn("area_codigo", error.exception.message_dict)

    def test_action_dates_and_operational_state_are_validated(self):
        self.action.fim_previsto = date(2029, 1, 1)
        with self.assertRaises(ValidationError):
            self.action.full_clean()

        self.action.fim_previsto = date(2026, 12, 1)
        self.action.estado = AcaoFormacao.Estado.EM_CURSO
        with self.assertRaises(ValidationError):
            self.action.full_clean()

        self.action.inicio_real = date(2026, 10, 2)
        self.action.estado = AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO
        with self.assertRaises(ValidationError):
            self.action.full_clean()

    def test_empty_action_has_no_derived_typology(self):
        self.action.recalcular_resumos()

        self.assertEqual(self.action.tipologia, AcaoFormacao.Tipologia.POR_DEFINIR)
        self.assertEqual(self.action.horas_totais, Decimal("0"))
        self.assertEqual(str(self.action), "Programação web")
