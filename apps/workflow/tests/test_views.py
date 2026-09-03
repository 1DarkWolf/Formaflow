from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.candidaturas.models import Candidatura
from apps.documentos.tests.factories import DocumentFixtureMixin

from ..models import TermoAceitacao


class WorkflowViewTests(DocumentFixtureMixin, TestCase):
    def test_visible_manager_can_open_timeline_and_transition_confirmation(self):
        self.client.force_login(self.manager)

        detail = self.client.get(
            reverse("workflow:detalhe", kwargs={"public_id": self.application.public_id})
        )
        action = self.client.get(
            reverse(
                "workflow:acontecimento",
                kwargs={"public_id": self.application.public_id, "codigo": "TR-002"},
            )
        )

        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Linha temporal")
        self.assertContains(detail, "TR-001")
        self.assertEqual(action.status_code, 200)
        self.assertContains(action, "Validar candidatura")

    def test_outsider_cannot_discover_workflow_or_request(self):
        self.client.force_login(self.outsider)

        detail = self.client.get(
            reverse("workflow:detalhe", kwargs={"public_id": self.application.public_id})
        )
        request_form = self.client.get(
            reverse("workflow:novo_pedido", kwargs={"public_id": self.application.public_id})
        )

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(request_form.status_code, 404)

    def test_term_screen_explains_that_late_receipt_is_not_an_automatic_decision(self):
        Candidatura.objects.filter(pk=self.application.pk).update(
            estado_atual=Candidatura.Estado.APROVADA_AGUARDA_TERMO
        )
        TermoAceitacao.objects.create(
            candidatura=self.application,
            estado=TermoAceitacao.Estado.PENDENTE,
            notificado_em=timezone.now(),
            data_limite=timezone.now(),
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("workflow:termo", kwargs={"public_id": self.application.public_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nunca uma decisão automática")
        self.assertContains(response, "Guardar termo PDF")

    def test_closure_start_form_is_available_only_in_the_tracking_state(self):
        self.client.force_login(self.manager)
        url = reverse(
            "workflow:iniciar_encerramento",
            kwargs={"public_id": self.application.public_id},
        )

        denied = self.client.get(url)
        Candidatura.objects.filter(pk=self.application.pk).update(
            estado_atual=Candidatura.Estado.APROVADA_ACOMPANHAMENTO
        )
        allowed = self.client.get(url)

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "Gerar checklist final")
