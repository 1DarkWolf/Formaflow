from datetime import date
from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.contas.constants import GRUPO_ADMINISTRADOR
from apps.contas.models import Utilizador
from apps.organizacoes.models import Empresa, EntidadeFormadora
from apps.regras.models import ConjuntoRegras, Feriado, ParametroRegra, TipoDocumento

PASSWORD = "Segura!2026Projeto"


class DemonstrationCommandTests(TestCase):
    def test_command_is_idempotent(self):
        output = StringIO()

        call_command("carregar_dados_demonstracao", stdout=output)
        first_counts = self.counts()
        call_command("carregar_dados_demonstracao", stdout=output)

        self.assertEqual(self.counts(), first_counts)
        self.assertEqual(first_counts, (1, 1, 1, 21, 9, 2))
        self.assertIn("sem criar duplicados", output.getvalue())

    @staticmethod
    def counts():
        return (
            Empresa.objects.count(),
            EntidadeFormadora.objects.count(),
            ConjuntoRegras.objects.count(),
            ParametroRegra.objects.count(),
            TipoDocumento.objects.count(),
            Feriado.objects.count(),
        )


class RuleViewsTests(TestCase):
    def setUp(self):
        self.administrator = Utilizador.objects.create_user(
            email="admin.view@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="View",
        )
        self.administrator.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        self.manager = Utilizador.objects.create_user(
            email="manager.view@example.test",
            password=PASSWORD,
            nome_proprio="Manager",
            apelido="View",
        )
        self.rules = ConjuntoRegras.objects.create(
            codigo="VIEW",
            versao=1,
            designacao="Regras da interface",
            vigente_desde=date(2026, 1, 1),
            fonte="Teste",
        )

    def test_administrator_can_see_and_publish_draft(self):
        self.client.force_login(self.administrator)
        page = self.client.get(reverse("regras:lista_conjuntos"))

        self.assertContains(page, "Regras da interface")
        self.assertContains(page, "Publicar versão")

        response = self.client.post(reverse("regras:publicar", args=[self.rules.pk]))
        self.assertRedirects(response, reverse("regras:lista_conjuntos"))
        self.rules.refresh_from_db()
        self.assertEqual(self.rules.estado, ConjuntoRegras.Estado.ATIVO)

    def test_non_administrator_cannot_see_draft_or_publish(self):
        self.client.force_login(self.manager)

        self.assertNotContains(
            self.client.get(reverse("regras:lista_conjuntos")),
            "Regras da interface",
        )
        response = self.client.post(reverse("regras:publicar", args=[self.rules.pk]))
        self.assertEqual(response.status_code, 403)

    def test_rule_list_requires_authentication(self):
        response = self.client.get(reverse("regras:lista_conjuntos"))

        self.assertEqual(response.status_code, 302)


class AdministrationPagesTests(TestCase):
    def test_technical_administrator_can_open_new_model_lists(self):
        administrator = Utilizador.objects.create_superuser(
            email="admin.tecnico@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Técnico",
        )
        self.client.force_login(administrator)

        organization_page = self.client.get(reverse("admin:organizacoes_empresa_changelist"))
        rules_page = self.client.get(reverse("admin:regras_conjuntoregras_changelist"))

        self.assertEqual(organization_page.status_code, 200)
        self.assertEqual(rules_page.status_code, 200)
