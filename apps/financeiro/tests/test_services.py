from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura
from apps.candidaturas.services import (
    adicionar_beneficiario,
    associar_participacao,
    criar_candidatura_empresarial,
)
from apps.documentos.tests.factories import DocumentFixtureMixin
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import EntidadeFormadora, VinculoLaboral
from apps.regras.models import ParametroRegra
from apps.workflow.models import Notificacao, Prazo

from ..models import ApoioFinanceiro, MovimentoFinanceiro, Restituicao
from ..selectors import apoios_visiveis_por, restituicoes_visiveis_por
from ..services import (
    atualizar_restituicao,
    calcular_apoio_formacao_desempregado,
    calcular_apoio_formacao_empregado,
    calcular_bolsa_formacao,
    calcular_estimativas_candidatura,
    calcular_subsidio_refeicao,
    confirmar_valores_oficiais,
    registar_movimento,
    registar_restituicao_oficial,
    registar_risco_restituicao,
    total_confirmado_apoio,
    validar_encerramento_financeiro,
)


class FinanceFixtureMixin(DocumentFixtureMixin):
    def setUp(self):
        super().setUp()
        parameters = (
            ("CFG-JANELA-APOIO", ParametroRegra.TipoValor.INTEIRO, 2, "anos"),
            ("CFG-EMP-HORAS", ParametroRegra.TipoValor.INTEIRO, 50, "horas"),
            (
                "CFG-EMP-VALOR-HORA",
                ParametroRegra.TipoValor.DECIMAL,
                4,
                "euros/hora",
            ),
            ("CFG-EMP-MONTANTE", ParametroRegra.TipoValor.DECIMAL, 175, "euros"),
            (
                "CFG-EMP-PERCENTAGEM",
                ParametroRegra.TipoValor.DECIMAL,
                90,
                "percentagem",
            ),
            ("CFG-DESEMP-HORAS", ParametroRegra.TipoValor.INTEIRO, 150, "horas"),
            ("CFG-DESEMP-MONTANTE", ParametroRegra.TipoValor.DECIMAL, 500, "euros"),
            ("CFG-IAS", ParametroRegra.TipoValor.DECIMAL, "438.81", "euros"),
            (
                "CFG-BOLSA-IAS-PERCENTAGEM",
                ParametroRegra.TipoValor.DECIMAL,
                35,
                "percentagem",
            ),
            (
                "CFG-REFEICAO-DIARIO",
                ParametroRegra.TipoValor.DECIMAL,
                "4.77",
                "euros/dia",
            ),
            (
                "CFG-RESTITUICAO",
                ParametroRegra.TipoValor.INTEIRO,
                60,
                "dias consecutivos",
            ),
        )
        ParametroRegra.objects.bulk_create(
            [
                ParametroRegra(
                    conjunto_regras=self.rules,
                    codigo=code,
                    designacao=code,
                    tipo_valor=value_type,
                    valor=value,
                    unidade=unit,
                )
                for code, value_type, value, unit in parameters
            ]
        )
        provider = EntidadeFormadora.objects.create(
            nipc="111111110", denominacao_legal="Formadora Financeira, Lda."
        )
        self.action = AcaoFormacao.objects.create(
            entidade_formadora=provider,
            designacao="Programação financeira",
            area_codigo="481",
            inicio_previsto=date(2026, 10, 1),
            fim_previsto=date(2026, 11, 1),
        )
        component = ComponenteFormacao(
            acao_formacao=self.action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.CNQ,
            codigo_cnq="UFCD-FIN",
            designacao="Componente financeira",
            area_codigo="481",
            horas=Decimal("50"),
        )
        component.full_clean()
        component.save()
        self.participation = associar_participacao(
            candidatura_id=self.application.pk,
            beneficiario=self.beneficiary,
            acao_formacao=self.action,
            horas_previstas=Decimal("20"),
            custo_declarado=Decimal("200"),
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        self.application.refresh_from_db()

    def calculate_support(self):
        calcular_estimativas_candidatura(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
        )
        return ApoioFinanceiro.objects.get(
            participacao=self.participation, tipo=ApoioFinanceiro.Tipo.FORMACAO
        )

    def mark_as_approved(self):
        self.application.__class__.objects.filter(pk=self.application.pk).update(
            estado_atual=self.application.Estado.APROVADA_ACOMPANHAMENTO
        )
        BeneficiarioCandidatura.objects.filter(pk=self.beneficiary.pk).update(
            resultado=BeneficiarioCandidatura.Resultado.DEFERIDA
        )
        self.application.refresh_from_db()
        self.beneficiary.refresh_from_db()

    def confirm_support(self):
        support = self.calculate_support()
        self.mark_as_approved()
        return confirmar_valores_oficiais(
            apoio_id=support.pk,
            utilizador=self.manager,
            valor_aprovado=support.valor_estimado,
            valor_final=support.valor_estimado,
            confirmado_em=timezone.now(),
            referencia_externa="DEC-FIN-TESTE",
        )


class CalculatorTests(TestCase):
    def test_employed_limits_cost_and_third_party_funding(self):
        result = calcular_apoio_formacao_empregado(
            horas=50,
            custo=100,
            financiamento_terceiros=20,
            horas_disponiveis=50,
            montante_disponivel=175,
            valor_hora=4,
            percentagem_maxima=90,
        )

        self.assertEqual(result["valor"], Decimal("72.00"))
        self.assertEqual(result["limite_percentagem"], Decimal("72.00"))

    def test_unemployed_limits_hours_and_amount(self):
        result = calcular_apoio_formacao_desempregado(
            horas=200,
            custo=700,
            horas_disponiveis=150,
            montante_disponivel=500,
        )

        self.assertEqual(result["valor"], Decimal("500.00"))
        self.assertEqual(result["horas_elegiveis"], Decimal("150"))
        self.assertTrue(result["horas_excedidas"])

    def test_social_support_formulas_use_exact_boundaries(self):
        meals = calcular_subsidio_refeicao(
            duracoes_diarias=[Decimal("3"), Decimal("2.99"), Decimal("4")],
            valor_diario=Decimal("4.77"),
        )
        scholarship = calcular_bolsa_formacao(horas=30, ias=Decimal("438.81"), percentagem_ias=35)

        self.assertEqual(meals, {"dias_elegiveis": 2, "valor": Decimal("9.54")})
        self.assertEqual(scholarship, Decimal("35.44"))


class FinancialServiceTests(FinanceFixtureMixin, TestCase):
    def test_estimate_never_becomes_official_without_provenance(self):
        support = self.calculate_support()

        self.assertEqual(support.valor_estimado, Decimal("80.00"))
        self.assertIsNone(support.valor_aprovado)
        support.valor_aprovado = Decimal("80")
        with self.assertRaises(ValidationError):
            support.full_clean()

        self.mark_as_approved()
        confirmed = confirmar_valores_oficiais(
            apoio_id=support.pk,
            utilizador=self.manager,
            valor_aprovado=Decimal("75"),
            valor_final=Decimal("70"),
            confirmado_em=timezone.now(),
            referencia_externa="DEC-001",
        )
        self.assertEqual(confirmed.valor_estimado, Decimal("80.00"))
        self.assertEqual(confirmed.valor_aprovado, Decimal("75.00"))
        self.assertEqual(confirmed.valor_final, Decimal("70.00"))
        self.assertEqual(confirmed.movimentos.filter(estado="PREVISTO").count(), 2)

    def test_window_deducts_prior_approved_hours_and_amount(self):
        previous_application = criar_candidatura_empresarial(
            criada_por=self.manager,
            titular_empresa=self.company,
            conjunto_regras=self.rules,
        )
        previous_beneficiary = adicionar_beneficiario(
            candidatura_id=previous_application.pk,
            candidato=self.candidate,
            utilizador=self.manager,
            versao_esperada=previous_application.versao,
        )
        previous_application.refresh_from_db()
        previous_participation = associar_participacao(
            candidatura_id=previous_application.pk,
            beneficiario=previous_beneficiary,
            acao_formacao=self.action,
            horas_previstas=Decimal("40"),
            custo_declarado=Decimal("200"),
            utilizador=self.manager,
            versao_esperada=previous_application.versao,
        )
        previous = ApoioFinanceiro(
            beneficiario=previous_beneficiary,
            participacao=previous_participation,
            tipo=ApoioFinanceiro.Tipo.FORMACAO,
            valor_estimado=Decimal("150"),
            valor_aprovado=Decimal("150"),
            conjunto_regras=self.rules,
            decomposicao_calculo={"horas_elegiveis": "40"},
            confirmado_em=timezone.now() - timedelta(days=1),
            confirmado_por=self.manager,
            referencia_externa="DEC-ANTERIOR",
        )
        previous.full_clean()
        previous.save()

        support = self.calculate_support()

        self.assertEqual(support.valor_estimado, Decimal("25.00"))
        self.assertEqual(support.decomposicao_calculo["horas_consumidas"], "40")

    def test_movements_are_idempotent_and_total_only_confirmed(self):
        support = self.confirm_support()
        movement = registar_movimento(
            apoio_id=support.pk,
            utilizador=self.manager,
            tipo=MovimentoFinanceiro.Tipo.PRIMEIRA_PRESTACAO,
            direcao=MovimentoFinanceiro.Direcao.CREDITO,
            valor=Decimal("40"),
            estado=MovimentoFinanceiro.Estado.CONFIRMADO,
            efetivado_em=timezone.now(),
            referencia_externa="PAG-001",
            chave_idempotencia="pagamento-1",
        )
        repeated = registar_movimento(
            apoio_id=support.pk,
            utilizador=self.manager,
            tipo=MovimentoFinanceiro.Tipo.PRIMEIRA_PRESTACAO,
            direcao=MovimentoFinanceiro.Direcao.CREDITO,
            valor=Decimal("999"),
            estado=MovimentoFinanceiro.Estado.CONFIRMADO,
            efetivado_em=timezone.now(),
            referencia_externa="PAG-REPETIDO",
            chave_idempotencia="pagamento-1",
        )
        registar_movimento(
            apoio_id=support.pk,
            utilizador=self.manager,
            tipo=MovimentoFinanceiro.Tipo.REMANESCENTE,
            direcao=MovimentoFinanceiro.Direcao.CREDITO,
            valor=Decimal("40"),
            estado=MovimentoFinanceiro.Estado.FALHOU,
            chave_idempotencia="falhou-1",
        )
        registar_movimento(
            apoio_id=support.pk,
            utilizador=self.manager,
            tipo=MovimentoFinanceiro.Tipo.AJUSTE,
            direcao=MovimentoFinanceiro.Direcao.DEBITO,
            valor=Decimal("5"),
            estado=MovimentoFinanceiro.Estado.CONFIRMADO,
            efetivado_em=timezone.now(),
            referencia_externa="AJUSTE-001",
            chave_idempotencia="ajuste-1",
        )

        self.assertEqual(movement.pk, repeated.pk)
        self.assertEqual(total_confirmado_apoio(support), Decimal("35.00"))

    def test_risk_only_creates_task_but_official_decision_creates_deadline(self):
        self.mark_as_approved()
        task = registar_risco_restituicao(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            motivo="Pagamento potencialmente indevido.",
            chave_idempotencia="risco-1",
        )

        self.assertEqual(Restituicao.objects.count(), 0)
        self.assertEqual(task.tipo, "ANALISAR_RISCO_RESTITUICAO")
        self.assertTrue(Notificacao.objects.filter(tarefa=task).exists())

        notified = timezone.now().replace(microsecond=0)
        refund = registar_restituicao_oficial(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            beneficiario=self.beneficiary,
            notificada_em=notified,
            valor=Decimal("50"),
            motivo="Decisão oficial de restituição.",
            referencia_externa="REST-001",
            chave_idempotencia="restituicao-1",
        )
        self.assertEqual(refund.data_limite, notified + timedelta(days=60))
        self.assertEqual(refund.prazo.unidade, Prazo.Unidade.DIAS_CONSECUTIVOS)

        partial = atualizar_restituicao(
            restituicao_id=refund.pk,
            utilizador=self.manager,
            valor_restituido=Decimal("20"),
        )
        self.assertEqual(partial.estado, Restituicao.Estado.PARCIAL)
        completed = atualizar_restituicao(
            restituicao_id=refund.pk,
            utilizador=self.manager,
            valor_restituido=Decimal("50"),
            regularizada_em=timezone.now(),
            referencia_externa="REST-PAGA",
        )
        self.assertEqual(completed.estado, Restituicao.Estado.PAGA)
        completed.prazo.refresh_from_db()
        self.assertEqual(completed.prazo.estado, Prazo.Estado.CUMPRIDO)

    def test_scope_hides_other_beneficiaries_and_outsider_cannot_calculate(self):
        second_candidate = self.make_candidate(
            "financeiro.segundo@example.test", "100000029", "Segundo", "Financeiro"
        )
        VinculoLaboral.objects.create(
            candidato=second_candidate,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=timezone.localdate() - timedelta(days=10),
        )
        second_beneficiary = adicionar_beneficiario(
            candidatura_id=self.application.pk,
            candidato=second_candidate,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        ApoioFinanceiro.objects.create(
            beneficiario=second_beneficiary,
            tipo=ApoioFinanceiro.Tipo.BOLSA,
            valor_estimado=Decimal("10"),
            conjunto_regras=self.rules,
        )
        own_support = self.calculate_support()
        self.mark_as_approved()
        registar_restituicao_oficial(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            notificada_em=timezone.now(),
            valor=Decimal("15"),
            motivo="Restituição global da entidade.",
            referencia_externa="REST-GLOBAL",
            chave_idempotencia="rest-global",
        )

        visible = apoios_visiveis_por(self.candidate.utilizador, self.application)
        self.assertEqual(list(visible), [own_support])
        self.assertFalse(
            restituicoes_visiveis_por(self.candidate.utilizador, self.application).exists()
        )
        with self.assertRaises(PermissionDenied):
            calcular_estimativas_candidatura(
                candidatura_id=self.application.pk,
                utilizador=self.outsider,
            )

    def test_explicit_no_payment_resolves_planned_movements(self):
        self.confirm_support()

        self.assertTrue(
            MovimentoFinanceiro.objects.filter(estado=MovimentoFinanceiro.Estado.PREVISTO).exists()
        )
        validar_encerramento_financeiro(
            candidatura=self.application,
            utilizador=self.manager,
            sem_pagamento=True,
            motivo="Decisão oficial sem pagamento.",
        )
        self.assertFalse(
            MovimentoFinanceiro.objects.filter(estado=MovimentoFinanceiro.Estado.PREVISTO).exists()
        )
