from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura
from apps.candidaturas.services import (
    adicionar_beneficiario,
    associar_participacao,
    definir_conta_pagamento,
    executar_verificacoes_basicas,
)
from apps.documentos.models import EstadoDocumento, SnapshotSubmissao
from apps.documentos.services import (
    carregar_documento_workflow,
    carregar_para_requisito,
    dispensar_requisito,
    gerar_checklist_preparacao,
    validar_versao,
)
from apps.documentos.tests.factories import DocumentFixtureMixin, pdf_upload
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import EntidadeFormadora, VinculoLaboral
from apps.organizacoes.services import criar_conta_pagamento
from apps.regras.models import ParametroRegra

from ..exceptions import ConflitoWorkflow, TransicaoInvalida
from ..models import (
    Notificacao,
    PedidoElementos,
    Prazo,
    QuestaoPedido,
    RespostaQuestao,
    SuspensaoPrazo,
    Tarefa,
    TermoAceitacao,
    TransicaoCandidatura,
)
from ..services import (
    aplicar_transicao,
    corrigir_limite_prazo,
    guardar_resposta_rascunho,
    registar_decisao,
    registar_pedido_elementos,
    registar_resposta_completa,
)

VALID_IBAN = "PT50000201231234567890154"


class WorkflowServiceTests(DocumentFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        ParametroRegra.objects.bulk_create(
            [
                ParametroRegra(
                    conjunto_regras=self.rules,
                    codigo=code,
                    designacao=code,
                    tipo_valor=ParametroRegra.TipoValor.INTEIRO,
                    valor=value,
                    unidade="dias úteis",
                )
                for code, value in (
                    ("CFG-ANALISE-PRAZO", 30),
                    ("CFG-ELEMENTOS-PRAZO", 10),
                    ("CFG-ACEITACAO-PRAZO", 10),
                )
            ]
        )
        self.second_candidate = self.make_candidate(
            "segundo.workflow@example.test", "100000029", "Segundo", "Beneficiário"
        )
        VinculoLaboral.objects.create(
            candidato=self.second_candidate,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=timezone.localdate() - timedelta(days=20),
        )
        self.second_beneficiary = adicionar_beneficiario(
            candidatura_id=self.application.pk,
            candidato=self.second_candidate,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        self.application.refresh_from_db()
        self.base_time = (timezone.now() + timedelta(minutes=1)).replace(
            second=0,
            microsecond=0,
        )

    def _prepare_application(self):
        provider = EntidadeFormadora.objects.create(
            nipc="111111110",
            denominacao_legal="Formadora Workflow, Lda.",
        )
        action = AcaoFormacao.objects.create(
            entidade_formadora=provider,
            designacao="Programação web para workflow",
            area_codigo="481",
            inicio_previsto=date(2026, 10, 1),
            fim_previsto=date(2026, 11, 1),
        )
        component = ComponenteFormacao(
            acao_formacao=action,
            ordem=1,
            tipo=ComponenteFormacao.Tipo.CNQ,
            codigo_cnq="UFCD-WORKFLOW",
            designacao="Componente de workflow",
            area_codigo="481",
            horas=Decimal("25"),
        )
        component.full_clean()
        component.save()
        for beneficiary in self.application.beneficiarios.order_by("pk"):
            associar_participacao(
                candidatura_id=self.application.pk,
                beneficiario=beneficiary,
                acao_formacao=action,
                horas_previstas=Decimal("25"),
                custo_declarado=Decimal("150"),
                utilizador=self.manager,
                versao_esperada=self.application.versao,
            )
            self.application.refresh_from_db()
        account = criar_conta_pagamento(
            iban=VALID_IBAN,
            nome_titular=self.company.denominacao_legal,
            empresa=self.company,
            principal=True,
        )
        definir_conta_pagamento(
            candidatura_id=self.application.pk,
            conta_pagamento=account,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        self.application.refresh_from_db()
        requirements = gerar_checklist_preparacao(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
        )
        evidence = carregar_para_requisito(
            requisito_id=requirements[0].pk,
            ficheiro=pdf_upload("evidencia.pdf"),
            utilizador=self.manager,
        )
        validar_versao(
            versao_id=evidence.pk,
            utilizador=self.administrator,
            resultado=evidence.EstadoValidacao.VALIDO,
        )
        for requirement in requirements[1:]:
            dispensar_requisito(
                requisito_id=requirement.pk,
                utilizador=self.manager,
                motivo="Dispensa controlada para o cenário de teste.",
            )
        executar_verificacoes_basicas(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
        )
        self.application.refresh_from_db()
        transition = aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-002",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="preparar-1",
            efetiva_em=self.base_time,
            confirmacao=True,
            avisos_reconhecidos=True,
        )
        self.application.refresh_from_db()
        self.evidence = evidence
        return transition

    def _submit_and_analyse(self):
        self._prepare_application()
        submission = aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-004",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="submeter-1",
            efetiva_em=self.base_time + timedelta(hours=1),
            origem=TransicaoCandidatura.Origem.IEFPONLINE,
            referencia_externa="IEFP-2026-001",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        analysis = aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-006",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="analise-1",
            efetiva_em=self.base_time + timedelta(hours=2),
            origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
            referencia_externa="COM-ANALISE-001",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        return submission, analysis

    def _request_elements(self, *, questions=None):
        self._submit_and_analyse()
        transition, request = registar_pedido_elementos(
            candidatura_id=self.application.pk,
            questoes=questions
            or [
                {"texto": "Confirme os dados declarados."},
                {"texto": "Justifique o custo da formação."},
            ],
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="pedido-1",
            recebido_em=self.base_time + timedelta(days=1),
            referencia_externa="PEDIDO-001",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        return transition, request

    def test_creation_is_recorded_and_direct_state_change_is_rejected(self):
        creation = self.application.transicoes.get(codigo="TR-001")

        self.assertEqual((creation.versao_anterior, creation.versao_nova), (0, 1))
        self.assertIsNone(creation.estado_anterior)
        self.application.estado_atual = Candidatura.Estado.SUBMETIDA
        with self.assertRaises(ValidationError):
            self.application.save()

    def test_preparation_reopen_and_abandon_follow_the_declared_matrix(self):
        preparation = self._prepare_application()
        self.assertEqual(preparation.estado_novo, Candidatura.Estado.PRONTA_SUBMISSAO)

        with self.assertRaises(ValidationError):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-003",
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="reabrir-data-invalida",
                efetiva_em=self.base_time - timedelta(seconds=1),
                confirmacao=True,
            )

        aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-003",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="reabrir-1",
            efetiva_em=self.base_time + timedelta(minutes=10),
            confirmacao=True,
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.RASCUNHO)

        aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-005",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="abandonar-1",
            efetiva_em=self.base_time + timedelta(minutes=20),
            motivo="A empresa decidiu não prosseguir.",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.RASCUNHO_ARQUIVADO)

    def test_invalid_origin_role_and_stale_version_leave_no_effects(self):
        initial_version = self.application.versao
        initial_count = self.application.transicoes.count()
        with self.assertRaises(TransicaoInvalida):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-004",
                utilizador=self.manager,
                versao_esperada=initial_version,
                chave_idempotencia="invalid-origin",
                efetiva_em=self.base_time,
                origem=TransicaoCandidatura.Origem.IEFPONLINE,
                confirmacao=True,
            )
        with self.assertRaises(PermissionDenied):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-002",
                utilizador=self.outsider,
                versao_esperada=initial_version,
                chave_idempotencia="invalid-role",
                efetiva_em=self.base_time,
                confirmacao=True,
                avisos_reconhecidos=True,
            )
        with self.assertRaises(ConflitoWorkflow):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-002",
                utilizador=self.manager,
                versao_esperada=initial_version - 1,
                chave_idempotencia="stale-version",
                efetiva_em=self.base_time,
                confirmacao=True,
                avisos_reconhecidos=True,
            )

        self.application.refresh_from_db()
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.RASCUNHO)
        self.assertEqual(self.application.transicoes.count(), initial_count)

    def test_submission_is_atomic_and_idempotent(self):
        self._prepare_application()
        kwargs = {
            "candidatura_id": self.application.pk,
            "codigo": "TR-004",
            "utilizador": self.manager,
            "versao_esperada": self.application.versao,
            "chave_idempotencia": "submission-idempotent",
            "efetiva_em": self.base_time + timedelta(hours=1),
            "origem": TransicaoCandidatura.Origem.IEFPONLINE,
            "referencia_externa": "IEFP-IDEMPOTENT",
            "confirmacao": True,
        }
        first = aplicar_transicao(**kwargs)
        second = aplicar_transicao(**kwargs)
        self.application.refresh_from_db()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.SUBMETIDA)
        self.assertEqual(self.application.transicoes.filter(codigo="TR-004").count(), 1)
        self.assertEqual(self.application.snapshots_submissao.count(), 1)
        snapshot = self.application.snapshots_submissao.get()
        self.assertEqual(snapshot.transicao, first)
        self.assertEqual(self.application.prazos.filter(tipo=Prazo.Tipo.DECISAO).count(), 1)
        self.assertEqual(self.application.tarefas.filter(tipo="ACOMPANHAR_ANALISE").count(), 1)
        self.assertTrue(Notificacao.objects.filter(candidatura=self.application).exists())

    def test_follow_up_document_is_private_and_limited_to_the_application_scope(self):
        self._prepare_application()
        aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-004",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="submission-for-evidence",
            efetiva_em=self.base_time + timedelta(hours=1),
            origem=TransicaoCandidatura.Origem.IEFPONLINE,
            confirmacao=True,
        )
        self.application.refresh_from_db()

        version = carregar_documento_workflow(
            candidatura_id=self.application.pk,
            tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
            ficheiro=pdf_upload("comunicacao.pdf"),
            utilizador=self.manager,
            titulo="Comunicação externa",
        )

        self.assertEqual(version.documento.candidatura, self.application)
        self.assertEqual(version.documento.fase, "ANALISE")
        self.assertNotIn("comunicacao", version.ficheiro.chave_armazenamento)
        with self.assertRaises(PermissionDenied):
            carregar_documento_workflow(
                candidatura_id=self.application.pk,
                tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
                ficheiro=pdf_upload("indevido.pdf"),
                utilizador=self.outsider,
            )

    def test_submission_with_document_blocker_rolls_back_transition_and_snapshot(self):
        self._prepare_application()
        self.application.requisitos_documentais.exclude(estado=EstadoDocumento.DISPENSADO).update(
            estado=EstadoDocumento.INVALIDO
        )
        before = self.application.transicoes.count()

        with self.assertRaises(ValidationError):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-004",
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="blocked-submission",
                efetiva_em=self.base_time + timedelta(hours=1),
                origem=TransicaoCandidatura.Origem.IEFPONLINE,
                confirmacao=True,
            )

        self.application.refresh_from_db()
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.PRONTA_SUBMISSAO)
        self.assertEqual(self.application.transicoes.count(), before)
        self.assertFalse(self.application.snapshots_submissao.exists())

    def test_request_suspends_deadline_and_repetition_does_not_duplicate_effects(self):
        self._submit_and_analyse()
        decision_deadline = self.application.prazos.get(tipo=Prazo.Tipo.DECISAO)
        kwargs = {
            "candidatura_id": self.application.pk,
            "questoes": [{"texto": "Envie um esclarecimento."}],
            "utilizador": self.manager,
            "versao_esperada": self.application.versao,
            "chave_idempotencia": "request-idempotent",
            "recebido_em": self.base_time + timedelta(days=1),
            "referencia_externa": "PEDIDO-IDEMPOTENT",
            "confirmacao": True,
        }
        first_transition, first_request = registar_pedido_elementos(**kwargs)
        second_transition, second_request = registar_pedido_elementos(**kwargs)
        self.application.refresh_from_db()
        decision_deadline.refresh_from_db()

        self.assertEqual(first_transition.pk, second_transition.pk)
        self.assertIsNone(second_request)
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.AGUARDA_ELEMENTOS)
        self.assertEqual(PedidoElementos.objects.filter(candidatura=self.application).count(), 1)
        self.assertEqual(first_request.questoes.count(), 1)
        self.assertEqual(decision_deadline.estado, Prazo.Estado.SUSPENSO)
        self.assertEqual(decision_deadline.suspensoes.filter(fim_em__isnull=True).count(), 1)
        self.assertEqual(first_request.tarefas.count(), 1)

    def test_incomplete_answer_is_rejected_and_complete_answer_resumes_deadline(self):
        _, additional_request = self._request_elements()
        old_deadline = self.application.prazos.get(tipo=Prazo.Tipo.DECISAO)
        old_limit = old_deadline.limite_calculado
        response_time = self.base_time + timedelta(days=3)

        with self.assertRaises(ValidationError):
            registar_resposta_completa(
                pedido_id=additional_request.pk,
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="incomplete-answer",
                efetiva_em=response_time,
                confirmacao=True,
            )
        self.application.refresh_from_db()
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.AGUARDA_ELEMENTOS)

        for question in additional_request.questoes.all():
            guardar_resposta_rascunho(
                questao_id=question.pk,
                utilizador=self.manager,
                texto=f"Resposta completa à questão {question.ordem}.",
            )
        transition = registar_resposta_completa(
            pedido_id=additional_request.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="complete-answer",
            efetiva_em=response_time,
            confirmacao=True,
        )
        repeated = registar_resposta_completa(
            pedido_id=additional_request.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="complete-answer",
            efetiva_em=response_time,
            confirmacao=True,
        )
        self.application.refresh_from_db()
        old_deadline.refresh_from_db()
        additional_request.refresh_from_db()
        suspension = old_deadline.suspensoes.get()

        self.assertEqual(transition.pk, repeated.pk)
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.EM_ANALISE)
        self.assertEqual(additional_request.estado, PedidoElementos.Estado.RESPONDIDO)
        self.assertEqual(old_deadline.estado, Prazo.Estado.ATIVO)
        self.assertEqual(suspension.fim_em, response_time)
        self.assertEqual(
            old_deadline.limite_calculado,
            old_limit + (response_time - suspension.inicio_em),
        )
        self.assertFalse(additional_request.tarefas.exclude(estado=Tarefa.Estado.CONCLUIDA))
        self.assertEqual(
            RespostaQuestao.objects.filter(estado=RespostaQuestao.Estado.SUBMETIDA).count(),
            2,
        )

    def test_beneficiary_can_store_and_attach_a_document_requested_for_them(self):
        _, additional_request = self._request_elements(
            questions=[
                {
                    "texto": "Anexe o comprovativo pedido.",
                    "destinatario": QuestaoPedido.Destinatario.BENEFICIARIO,
                    "beneficiario": self.beneficiary,
                    "exige_texto": False,
                    "exige_documento": True,
                    "tipo_documento": self.document_types["IDENTIFICACAO_CIVIL"],
                }
            ]
        )
        question = additional_request.questoes.get()
        version = carregar_documento_workflow(
            candidatura_id=self.application.pk,
            tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
            ficheiro=pdf_upload("resposta-beneficiario.pdf"),
            utilizador=self.candidate.utilizador,
            beneficiario=self.beneficiary,
        )
        answer = guardar_resposta_rascunho(
            questao_id=question.pk,
            utilizador=self.candidate.utilizador,
            versoes_documentos=[version],
        )

        self.assertEqual(answer.autor, self.candidate.utilizador)
        self.assertQuerySetEqual(answer.versoes_documentos.all(), [version])
        with self.assertRaises(PermissionDenied):
            carregar_documento_workflow(
                candidatura_id=self.application.pk,
                tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
                ficheiro=pdf_upload("outra-pessoa.pdf"),
                utilizador=self.second_candidate.utilizador,
                beneficiario=self.beneficiary,
            )

    def test_database_rejects_two_open_suspensions_for_same_deadline(self):
        _, additional_request = self._request_elements()
        deadline = self.application.prazos.get(tipo=Prazo.Tipo.DECISAO)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SuspensaoPrazo.objects.create(
                prazo=deadline,
                pedido_elementos=additional_request,
                inicio_em=self.base_time + timedelta(days=2),
                origem=SuspensaoPrazo.Origem.CALCULADA,
                motivo="Sobreposição indevida.",
                registada_por=self.manager,
            )

    def test_partial_decision_updates_individual_and_global_results(self):
        self._submit_and_analyse()
        beneficiaries = list(self.application.beneficiarios.order_by("pk"))
        transition = registar_decisao(
            candidatura_id=self.application.pk,
            resultados={
                beneficiaries[0].pk: BeneficiarioCandidatura.Resultado.DEFERIDA,
                beneficiaries[1].pk: BeneficiarioCandidatura.Resultado.INDEFERIDA,
            },
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="decision-partial",
            efetiva_em=self.base_time + timedelta(days=2),
            evidencia=self.evidence,
            referencia_externa="DECISAO-001",
            motivos_beneficiarios={beneficiaries[1].pk: "Não elegível."},
            confirmacao=True,
        )
        self.application.refresh_from_db()

        self.assertEqual(transition.codigo, "TR-009")
        self.assertEqual(
            self.application.resultado_decisao,
            Candidatura.ResultadoDecisao.DEFERIDA_PARCIAL,
        )
        self.assertEqual(
            self.application.estado_atual,
            Candidatura.Estado.APROVADA_AGUARDA_TERMO,
        )
        self.assertEqual(
            list(self.application.beneficiarios.order_by("pk").values_list("resultado", flat=True)),
            [
                BeneficiarioCandidatura.Resultado.DEFERIDA,
                BeneficiarioCandidatura.Resultado.INDEFERIDA,
            ],
        )
        self.assertTrue(TermoAceitacao.objects.filter(candidatura=self.application).exists())
        self.assertTrue(self.application.prazos.filter(tipo=Prazo.Tipo.TERMO).exists())

    def _assert_uniform_decision(self, outcome, code, final_state):
        self._submit_and_analyse()
        beneficiaries = list(self.application.beneficiarios.order_by("pk"))
        transition = registar_decisao(
            candidatura_id=self.application.pk,
            resultados={item.pk: outcome for item in beneficiaries},
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia=f"decision-{code}",
            efetiva_em=self.base_time + timedelta(days=2),
            evidencia=self.evidence,
            referencia_externa=f"DECISAO-{code}",
            motivo="Motivo oficial global.",
            motivos_beneficiarios={item.pk: "Motivo oficial individual." for item in beneficiaries},
            confirmacao=True,
        )
        self.application.refresh_from_db()
        self.assertEqual(transition.codigo, code)
        self.assertEqual(self.application.estado_atual, final_state)

    def test_uniform_negative_decision_uses_tr_010(self):
        self._assert_uniform_decision(
            BeneficiarioCandidatura.Resultado.INDEFERIDA,
            "TR-010",
            Candidatura.Estado.INDEFERIDA,
        )

    def test_uniform_archive_decision_uses_tr_011(self):
        self._assert_uniform_decision(
            BeneficiarioCandidatura.Resultado.ARQUIVADA,
            "TR-011",
            Candidatura.Estado.ARQUIVADA,
        )

    def test_withdrawal_and_deadline_correction_require_reasons(self):
        self._prepare_application()
        aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-004",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="submit-withdraw",
            efetiva_em=self.base_time + timedelta(hours=1),
            origem=TransicaoCandidatura.Origem.IEFPONLINE,
            confirmacao=True,
        )
        self.application.refresh_from_db()
        deadline = self.application.prazos.get(tipo=Prazo.Tipo.DECISAO)
        with self.assertRaises(ValidationError):
            corrigir_limite_prazo(
                prazo_id=deadline.pk,
                utilizador=self.manager,
                novo_limite=deadline.limite_calculado + timedelta(days=1),
                motivo="",
            )
        corrected = corrigir_limite_prazo(
            prazo_id=deadline.pk,
            utilizador=self.manager,
            novo_limite=deadline.limite_calculado + timedelta(days=1),
            motivo="Data indicada na comunicação oficial.",
        )
        self.assertEqual(corrected.limite_anterior, deadline.limite_calculado)

        with self.assertRaises(ValidationError):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-012",
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="withdraw-no-reason",
                efetiva_em=self.base_time + timedelta(days=1),
                origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
                confirmacao=True,
            )
        aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-012",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="withdraw-valid",
            efetiva_em=self.base_time + timedelta(days=1),
            origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
            motivo="Desistência confirmada no portal externo.",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        corrected.refresh_from_db()
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.DESISTIDA)
        self.assertEqual(corrected.estado, Prazo.Estado.CANCELADO)

    def test_transition_history_is_immutable(self):
        transition = self.application.transicoes.get(codigo="TR-001")
        transition.motivo = "Tentativa de alteração"
        with self.assertRaises(ValidationError):
            transition.save()
        with self.assertRaises(ValidationError):
            transition.delete()

    def test_snapshot_type_is_the_submission_snapshot(self):
        submission, _ = self._submit_and_analyse()
        snapshot = self.application.snapshots_submissao.get(transicao=submission)
        self.assertEqual(snapshot.finalidade, SnapshotSubmissao.Finalidade.SUBMISSAO)
