from django.test import TestCase
from django.urls import reverse

from apps.documentos.tests.factories import DocumentFixtureMixin


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
