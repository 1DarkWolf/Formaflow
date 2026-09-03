from django.test import SimpleTestCase
from django.urls import reverse


class HomeViewTests(SimpleTestCase):
    def test_home_page_confirms_current_project_status(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forma Flow")
        self.assertContains(response, "Candidaturas e formação num só fluxo")
        self.assertContains(response, "IMP-09 — Robustez e entrega")

    def test_home_applies_browser_security_headers(self):
        response = self.client.get(reverse("core:home"))

        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(
            response.headers["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=()",
        )

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


class ErrorViewTests(SimpleTestCase):
    def test_not_found_page_does_not_repeat_the_requested_path(self):
        secret_path = "/recurso-inexistente/identificador-confidencial/"

        response = self.client.get(secret_path)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Não foi possível concluir este pedido", status_code=404)
        self.assertNotContains(response, secret_path, status_code=404)
