from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.candidaturas.services import criar_candidatura_empresarial
from apps.documentos.tests.factories import DocumentFixtureMixin
from apps.workflow.models import Tarefa


class DashboardTests(DocumentFixtureMixin, TestCase):
    def test_manager_dashboard_shows_only_operational_priorities(self):
        Tarefa.objects.create(
            candidatura=self.application,
            atribuida_a=self.manager,
            tipo="REVER",
            titulo="Rever candidatura da empresa",
        )
        self.client.force_login(self.manager)

        response = self.client.get(reverse("contas:dashboard"))

        self.assertContains(response, "Gestão operacional")
        self.assertContains(response, "Rever candidatura da empresa")
        self.assertEqual(response.context["indicadores"]["candidaturas"], 1)

    def test_candidate_dashboard_uses_personal_role_and_assigned_tasks_only(self):
        Tarefa.objects.create(
            candidatura=self.application,
            atribuida_a=self.manager,
            tipo="INTERNA",
            titulo="Tarefa interna reservada",
        )
        self.client.force_login(self.candidate.utilizador)

        response = self.client.get(reverse("contas:dashboard"))

        self.assertContains(response, "Candidato")
        self.assertNotContains(response, "Tarefa interna reservada")
        self.assertEqual(response.context["indicadores"]["tarefas_abertas"], 0)

    def test_administrator_dashboard_shows_global_controls(self):
        self.client.force_login(self.administrator)

        response = self.client.get(reverse("contas:dashboard"))

        self.assertContains(response, "Administrador")
        self.assertContains(response, "Abrir administração técnica")

    def test_dashboard_query_count_does_not_grow_per_application_row(self):
        self.client.force_login(self.manager)
        with CaptureQueriesContext(connection) as initial_queries:
            self.client.get(reverse("contas:dashboard"))
        for _index in range(8):
            criar_candidatura_empresarial(
                criada_por=self.manager,
                titular_empresa=self.company,
                conjunto_regras=self.rules,
            )

        with CaptureQueriesContext(connection) as scaled_queries:
            response = self.client.get(reverse("contas:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(scaled_queries), len(initial_queries) + 1)
