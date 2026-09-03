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
from apps.documentos.models import EstadoDocumento, FaseDocumento, SnapshotSubmissao
from apps.documentos.services import (
    carregar_documento_workflow,
    carregar_para_requisito,
    dispensar_requisito,
    gerar_checklist_preparacao,
    validar_versao,
)
from apps.documentos.tests.factories import DocumentFixtureMixin, pdf_upload
from apps.financeiro.models import ApoioFinanceiro
from apps.financeiro.services import (
    calcular_estimativas_candidatura,
    confirmar_valores_oficiais,
)
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import EntidadeFormadora, VinculoLaboral
from apps.organizacoes.services import criar_conta_pagamento
from apps.regras.models import ParametroRegra

from ..exceptions import ConflitoWorkflow, TransicaoInvalida
from ..models import (
    Notificacao,
    PedidoElementos,
    PedidoEncerramento,
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
    associar_termo_recebido,
    confirmar_regularizacao_financeira,
    confirmar_termo_aceite,
    corrigir_estado_terminal,
    corrigir_limite_prazo,
    guardar_resposta_rascunho,
    iniciar_preparacao_encerramento,
    registar_conclusao_encerramento,
    registar_decisao,
    registar_pedido_elementos,
    registar_resposta_completa,
    registar_resultado_participacao,
    submeter_encerramento,
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
                    unidade=unit,
                )
                for code, value, unit in (
                    ("CFG-ANALISE-PRAZO", 30, "dias úteis"),
                    ("CFG-ELEMENTOS-PRAZO", 10, "dias úteis"),
                    ("CFG-ACEITACAO-PRAZO", 10, "dias úteis"),
                    ("CFG-PRIMEIRA-PRESTACAO", 5, "dias úteis"),
                    ("CFG-REMANESCENTE", 10, "dias úteis"),
                    ("CFG-ENCERRAMENTO", 2, "meses"),
                )
            ]
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
                for code, value_type, value, unit in (
                    (
                        "CFG-JANELA-APOIO",
                        ParametroRegra.TipoValor.INTEIRO,
                        2,
                        "anos",
                    ),
                    (
                        "CFG-EMP-HORAS",
                        ParametroRegra.TipoValor.INTEIRO,
                        50,
                        "horas",
                    ),
                    (
                        "CFG-EMP-VALOR-HORA",
                        ParametroRegra.TipoValor.DECIMAL,
                        4,
                        "euros/hora",
                    ),
                    (
                        "CFG-EMP-MONTANTE",
                        ParametroRegra.TipoValor.DECIMAL,
                        175,
                        "euros",
                    ),
                    (
                        "CFG-EMP-PERCENTAGEM",
                        ParametroRegra.TipoValor.DECIMAL,
                        90,
                        "percentagem",
                    ),
                    (
                        "CFG-DESEMP-HORAS",
                        ParametroRegra.TipoValor.INTEIRO,
                        150,
                        "horas",
                    ),
                    (
                        "CFG-DESEMP-MONTANTE",
                        ParametroRegra.TipoValor.DECIMAL,
                        500,
                        "euros",
                    ),
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

    def _approve_application(self):
        self._submit_and_analyse()
        outcomes = {
            beneficiary.pk: BeneficiarioCandidatura.Resultado.DEFERIDA
            for beneficiary in self.application.beneficiarios.all()
        }
        transition = registar_decisao(
            candidatura_id=self.application.pk,
            resultados=outcomes,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="decisao-aprovada",
            efetiva_em=self.base_time + timedelta(hours=3),
            evidencia=self.evidence,
            referencia_externa="DECISAO-APROVADA",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        return transition

    def _accept_term(self, *, late=False):
        self._approve_application()
        version = carregar_documento_workflow(
            candidatura_id=self.application.pk,
            tipo_documento=self.document_types["TERMO_ACEITACAO"],
            ficheiro=pdf_upload("termo-assinado.pdf"),
            utilizador=self.manager,
        )
        validar_versao(
            versao_id=version.pk,
            utilizador=self.administrator,
            resultado=version.EstadoValidacao.VALIDO,
        )
        term = self.application.termo_aceitacao
        received_at = (
            term.data_limite + timedelta(days=1) if late else self.base_time + timedelta(hours=4)
        )
        associar_termo_recebido(
            candidatura_id=self.application.pk,
            documento=version,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            recebido_em=received_at,
            tipo_assinatura=TermoAceitacao.TipoAssinatura.DIGITAL_PESSOAL,
        )
        effective_at = max(received_at, self.base_time + timedelta(hours=5))
        transition = confirmar_termo_aceite(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="confirmar-termo",
            efetiva_em=effective_at,
            confirmacao=True,
        )
        self.application.refresh_from_db()
        return transition

    def _complete_training(self):
        end_date = (self.base_time + timedelta(days=5)).date()
        start_date = (self.base_time + timedelta(days=1)).date()
        for participation in self.application.beneficiarios.order_by("pk").values_list(
            "participacoes_formacao__pk", flat=True
        ):
            registar_resultado_participacao(
                participacao_id=participation,
                utilizador=self.manager,
                estado=AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
                inicio_real=start_date,
                fim_real=end_date,
                horas_frequentadas=Decimal("25"),
                dias_tres_ou_mais_horas=5,
                custo_pago_formadora=Decimal("150"),
            )
        return end_date

    def _start_closure(self):
        self._accept_term()
        self._complete_training()
        transition = iniciar_preparacao_encerramento(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="iniciar-encerramento",
            efetiva_em=self.base_time + timedelta(days=6),
            confirmacao=True,
        )
        self.application.refresh_from_db()
        return transition

    def _submit_closure(self):
        self._start_closure()
        for requirement in self.application.requisitos_documentais.filter(
            fase=FaseDocumento.ENCERRAMENTO
        ):
            version = carregar_para_requisito(
                requisito_id=requirement.pk,
                ficheiro=pdf_upload(f"final-{requirement.pk}.pdf"),
                utilizador=self.manager,
            )
            validar_versao(
                versao_id=version.pk,
                utilizador=self.administrator,
                resultado=version.EstadoValidacao.VALIDO,
            )
        transition = submeter_encerramento(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="submeter-encerramento",
            efetiva_em=self.base_time + timedelta(days=7),
            referencia_externa="ENC-2026-001",
            evidencia=self.evidence,
            confirmacao=True,
        )
        self.application.refresh_from_db()
        return transition

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

    def test_term_out_of_time_alerts_but_can_be_accepted_after_validation(self):
        self._accept_term(late=True)
        self.application.refresh_from_db()
        term = self.application.termo_aceitacao

        self.assertTrue(term.fora_prazo)
        self.assertEqual(term.estado, TermoAceitacao.Estado.VALIDADO)
        self.assertEqual(
            self.application.estado_atual,
            Candidatura.Estado.APROVADA_ACOMPANHAMENTO,
        )
        self.assertTrue(
            Notificacao.objects.filter(
                candidatura=self.application,
                codigo="TERMO_FORA_PRAZO",
            ).exists()
        )
        self.assertTrue(self.application.prazos.filter(tipo=Prazo.Tipo.PRIMEIRA_PRESTACAO).exists())

    def test_term_confirmation_requires_a_valid_current_document(self):
        self._approve_application()
        version = carregar_documento_workflow(
            candidatura_id=self.application.pk,
            tipo_documento=self.document_types["TERMO_ACEITACAO"],
            ficheiro=pdf_upload("termo-pendente.pdf"),
            utilizador=self.manager,
        )
        associar_termo_recebido(
            candidatura_id=self.application.pk,
            documento=version,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            recebido_em=self.base_time + timedelta(hours=4),
            tipo_assinatura=TermoAceitacao.TipoAssinatura.MANUSCRITA,
        )
        with self.assertRaises(ValidationError):
            confirmar_termo_aceite(
                candidatura_id=self.application.pk,
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="termo-sem-validacao",
                efetiva_em=self.base_time + timedelta(hours=5),
                confirmacao=True,
            )
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.estado_atual,
            Candidatura.Estado.APROVADA_AGUARDA_TERMO,
        )

    def test_closure_preparation_requires_final_results_and_generates_checklist(self):
        self._accept_term()
        with self.assertRaises(ValidationError):
            iniciar_preparacao_encerramento(
                candidatura_id=self.application.pk,
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="encerramento-sem-resultados",
                efetiva_em=self.base_time + timedelta(days=6),
                confirmacao=True,
            )

        final_date = self._complete_training()
        transition = iniciar_preparacao_encerramento(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="encerramento-completo",
            efetiva_em=self.base_time + timedelta(days=6),
            confirmacao=True,
        )
        self.application.refresh_from_db()
        deadline = self.application.prazos.get(tipo=Prazo.Tipo.ENCERRAMENTO)

        self.assertEqual(transition.codigo, "TR-015")
        self.assertEqual(
            self.application.estado_atual,
            Candidatura.Estado.ENCERRAMENTO_PREPARACAO,
        )
        self.assertEqual(
            self.application.requisitos_documentais.filter(fase=FaseDocumento.ENCERRAMENTO).count(),
            6,
        )
        self.assertEqual(timezone.localtime(deadline.inicio_em).date(), final_date)
        self.assertEqual(
            timezone.localtime(deadline.limite_calculado).month,
            (final_date.month + 1) % 12 + 1,
        )

    def test_closure_submission_is_blocked_while_final_documents_are_missing(self):
        self._start_closure()
        with self.assertRaises(ValidationError):
            submeter_encerramento(
                candidatura_id=self.application.pk,
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="encerramento-sem-documentos",
                efetiva_em=self.base_time + timedelta(days=7),
                referencia_externa="ENC-INCOMPLETO",
                confirmacao=True,
            )
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.estado_atual,
            Candidatura.Estado.ENCERRAMENTO_PREPARACAO,
        )

    def test_complete_closure_path_supports_additional_elements(self):
        self._submit_closure()
        aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-017",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="analise-encerramento",
            efetiva_em=self.base_time + timedelta(days=8),
            origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
            referencia_externa="ANALISE-ENC-001",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        request_transition, request = registar_pedido_elementos(
            candidatura_id=self.application.pk,
            questoes=[{"texto": "Confirme o comprovativo final."}],
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="pedido-final",
            recebido_em=self.base_time + timedelta(days=9),
            referencia_externa="PEDIDO-ENC-001",
            confirmacao=True,
        )
        self.application.refresh_from_db()
        question = request.questoes.get()
        guardar_resposta_rascunho(
            questao_id=question.pk,
            utilizador=self.manager,
            texto="Comprovativo confirmado.",
        )
        response_transition = registar_resposta_completa(
            pedido_id=request.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="resposta-final",
            efetiva_em=self.base_time + timedelta(days=10),
            confirmacao=True,
        )
        self.application.refresh_from_db()
        calcular_estimativas_candidatura(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            usar_valores_finais=True,
        )
        for support in ApoioFinanceiro.objects.filter(
            beneficiario__candidatura=self.application,
            tipo=ApoioFinanceiro.Tipo.FORMACAO,
        ):
            confirmar_valores_oficiais(
                apoio_id=support.pk,
                utilizador=self.manager,
                valor_aprovado=support.valor_estimado,
                valor_final=support.valor_estimado,
                confirmado_em=self.base_time + timedelta(days=10),
                referencia_externa="DEC-FIN-001",
            )
        conclusion = registar_conclusao_encerramento(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="conclusao-final",
            efetiva_em=self.base_time + timedelta(days=11),
            resultado_final=PedidoEncerramento.ResultadoFinal.CONCLUIDO,
            referencia_externa="DEC-ENC-001",
            evidencia=self.evidence,
            confirmacao=True,
        )
        self.application.refresh_from_db()
        with self.assertRaises(ValidationError):
            confirmar_regularizacao_financeira(
                candidatura_id=self.application.pk,
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="regularizacao-pendente",
                efetiva_em=self.base_time + timedelta(days=12),
                regularizacao_confirmada=False,
                confirmacao=True,
            )
        closing = confirmar_regularizacao_financeira(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="regularizacao-confirmada",
            efetiva_em=self.base_time + timedelta(days=12),
            regularizacao_confirmada=True,
            sem_pagamento=True,
            motivo="Decisão oficial sem pagamentos adicionais.",
            confirmacao=True,
        )
        self.application.refresh_from_db()

        self.assertEqual(request_transition.codigo, "TR-018")
        self.assertEqual(request.fase, PedidoElementos.Fase.ENCERRAMENTO)
        self.assertEqual(response_transition.codigo, "TR-019")
        self.assertEqual(conclusion.codigo, "TR-020")
        self.assertEqual(closing.codigo, "TR-021")
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.ENCERRADA)
        self.assertEqual(
            self.application.pedido_encerramento.estado,
            PedidoEncerramento.Estado.CONCLUIDO,
        )
        self.assertTrue(
            self.application.snapshots_submissao.filter(
                finalidade=SnapshotSubmissao.Finalidade.ENCERRAMENTO
            ).exists()
        )

    def test_revocation_and_admin_correction_preserve_history(self):
        self._accept_term()
        revoked = aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-022",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="revogar",
            efetiva_em=self.base_time + timedelta(days=6),
            origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
            referencia_externa="REV-001",
            motivo="Revogação comunicada pelo IEFP.",
            evidencia=self.evidence,
            confirmacao=True,
        )
        self.application.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            corrigir_estado_terminal(
                candidatura_id=self.application.pk,
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="corrigir-sem-permissao",
                efetiva_em=self.base_time + timedelta(days=7),
                motivo="Tentativa sem perfil administrativo.",
                confirmacao=True,
            )
        correction = corrigir_estado_terminal(
            candidatura_id=self.application.pk,
            utilizador=self.administrator,
            versao_esperada=self.application.versao,
            chave_idempotencia="corrigir-revogacao",
            efetiva_em=self.base_time + timedelta(days=7),
            motivo="A comunicação foi associada ao processo errado.",
            confirmacao=True,
        )
        self.application.refresh_from_db()

        self.assertEqual(correction.codigo, "TR-023")
        self.assertEqual(correction.corrige_transicao, revoked)
        self.assertTrue(self.application.transicoes.filter(pk=revoked.pk).exists())
        self.assertEqual(
            self.application.estado_atual,
            Candidatura.Estado.APROVADA_ACOMPANHAMENTO,
        )
        self.assertFalse(
            self.application.beneficiarios.filter(
                resultado=BeneficiarioCandidatura.Resultado.REVOGADA
            ).exists()
        )

    def test_extinction_requires_official_evidence_and_blocks_document_changes(self):
        self._approve_application()
        with self.assertRaises(ValidationError):
            aplicar_transicao(
                candidatura_id=self.application.pk,
                codigo="TR-014",
                utilizador=self.manager,
                versao_esperada=self.application.versao,
                chave_idempotencia="extincao-sem-evidencia",
                efetiva_em=self.base_time + timedelta(days=1),
                origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
                motivo="Termo não devolvido.",
                confirmacao=True,
            )
        extinction = aplicar_transicao(
            candidatura_id=self.application.pk,
            codigo="TR-014",
            utilizador=self.manager,
            versao_esperada=self.application.versao,
            chave_idempotencia="extincao-oficial",
            efetiva_em=self.base_time + timedelta(days=1),
            origem=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
            referencia_externa="EXT-001",
            motivo="Termo não devolvido.",
            evidencia=self.evidence,
            confirmacao=True,
        )
        self.application.refresh_from_db()

        self.assertEqual(extinction.codigo, "TR-014")
        self.assertEqual(self.application.estado_atual, Candidatura.Estado.EXTINTA)
        with self.assertRaises(PermissionDenied):
            carregar_documento_workflow(
                candidatura_id=self.application.pk,
                tipo_documento=self.document_types["COMUNICACAO_IEFP"],
                ficheiro=pdf_upload("alteracao-terminal.pdf"),
                utilizador=self.manager,
            )

    def test_snapshot_type_is_the_submission_snapshot(self):
        submission, _ = self._submit_and_analyse()
        snapshot = self.application.snapshots_submissao.get(transicao=submission)
        self.assertEqual(snapshot.finalidade, SnapshotSubmissao.Finalidade.SUBMISSAO)
