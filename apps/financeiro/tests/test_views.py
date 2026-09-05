from decimal import Decimal
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..services import registar_restituicao_oficial
from .test_services import FinanceFixtureMixin


class FormMarkupParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.labels = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        if tag == "label" and attributes.get("for"):
            self.labels.append(attributes["for"])


class FinancialViewTests(FinanceFixtureMixin, TestCase):
    def test_financial_forms_have_unique_ids_and_linked_labels(self):
        self.calculate_support()
        self.client.force_login(self.manager)

        page = self.client.get(reverse("financeiro:detalhe", args=[self.application.public_id]))
        markup = FormMarkupParser()
        markup.feed(page.content.decode())

        self.assertEqual(len(markup.ids), len(set(markup.ids)))
        self.assertTrue(markup.labels)
        self.assertTrue(set(markup.labels).issubset(set(markup.ids)))
        self.assertContains(page, 'name="apoio"')
        self.assertContains(page, 'id="id_confirmacao_apoio"')
        self.assertContains(page, 'id="id_movimento_apoio"')

    def test_manager_can_calculate_and_open_financial_summary(self):
        self.client.force_login(self.manager)
        calculate_url = reverse("financeiro:calcular", args=[self.application.public_id])

        response = self.client.post(calculate_url, {"usar_valores_finais": ""})
        page = self.client.get(reverse("financeiro:detalhe", args=[self.application.public_id]))

        self.assertRedirects(
            response,
            reverse("financeiro:detalhe", args=[self.application.public_id]),
        )
        self.assertContains(page, "80,00")
        self.assertContains(page, "Registar valores oficiais")

    def test_candidate_sees_summary_without_management_forms(self):
        self.calculate_support()
        self.client.force_login(self.candidate.utilizador)

        page = self.client.get(reverse("financeiro:detalhe", args=[self.application.public_id]))

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "80,00")
        self.assertNotContains(page, "Registar valores oficiais")

    def test_manager_sees_regularization_form_after_official_refund(self):
        self.mark_as_approved()
        registar_restituicao_oficial(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            notificada_em=timezone.now(),
            valor=Decimal("25"),
            motivo="Decisão oficial para teste da página.",
            referencia_externa="REST-VIEW-001",
            chave_idempotencia="rest-view-1",
        )
        self.client.force_login(self.manager)

        page = self.client.get(reverse("financeiro:detalhe", args=[self.application.public_id]))

        self.assertContains(page, "Atualizar regularização de restituição")

    def test_outsider_cannot_open_financial_summary(self):
        self.client.force_login(self.outsider)

        page = self.client.get(reverse("financeiro:detalhe", args=[self.application.public_id]))

        self.assertEqual(page.status_code, 404)
