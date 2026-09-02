from django.test import SimpleTestCase
from django.urls import reverse


class HomeViewTests(SimpleTestCase):
    def test_home_page_confirms_current_project_status(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forma Flow")
        self.assertContains(response, "Candidaturas e formação num só fluxo")
        self.assertContains(response, "IMP-04 — Documentos e checklist")

    def test_home_rejects_unsafe_methods(self):
        response = self.client.post(reverse("core:home"))

        self.assertEqual(response.status_code, 405)


class HealthViewTests(SimpleTestCase):
    def test_health_returns_minimal_success_response(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"service": "formaflow", "status": "ok"})
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_health_rejects_unsafe_methods(self):
        response = self.client.post(reverse("core:health"))

        self.assertEqual(response.status_code, 405)
