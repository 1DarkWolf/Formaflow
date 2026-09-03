from django.test import TestCase
from django.urls import reverse

from apps.auditoria.models import RegistoAuditoria
from apps.documentos.tests.factories import DocumentFixtureMixin


class ApplicationReportingTests(DocumentFixtureMixin, TestCase):
    def test_list_filters_by_type_and_keeps_pagination_contract(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("candidaturas:lista"),
            {"tipo": "INDIVIDUAL", "estado": "ESTADO_INVALIDO"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filtros"]["tipo"], "INDIVIDUAL")
        self.assertEqual(response.context["filtros"]["estado"], "")
        self.assertEqual(response.context["candidaturas"].paginator.per_page, 12)

    def test_csv_export_is_minimal_scoped_and_audited(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("candidaturas:exportar_csv"),
            {"q": self.company.denominacao_legal},
            REMOTE_ADDR="192.0.2.20",
        )
        content = response.content.decode("utf-8-sig")

        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.application.public_id), content)
        self.assertNotIn(self.company.nipc, content)
        self.assertNotIn(self.candidate.nif, content)
        event = RegistoAuditoria.objects.get(acao="EXPORTAR_CANDIDATURAS_CSV")
        self.assertEqual(event.metadados["quantidade"], 1)
        self.assertNotIn(self.company.denominacao_legal, str(event.metadados))

    def test_outsider_export_has_no_application_rows(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("candidaturas:exportar_csv"))
        content = response.content.decode("utf-8-sig")

        self.assertEqual(len(content.strip().splitlines()), 1)
        self.assertNotIn(str(self.application.public_id), content)
