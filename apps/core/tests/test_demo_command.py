import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura
from apps.contas.models import Utilizador
from apps.financeiro.models import MovimentoFinanceiro
from apps.workflow.models import Notificacao, Prazo, SuspensaoPrazo

IN_MEMORY_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=IN_MEMORY_STORAGE)
class DemonstrationScenarioTests(TestCase):
    @patch.dict(os.environ, {"FORMAFLOW_DEMO_PASSWORD": "Demonstracao!2026Segura"})
    def test_command_builds_an_offline_scenario_without_duplicates(self):
        output = StringIO()

        call_command("carregar_cenario_demonstracao", stdout=output)
        first_counts = (
            Utilizador.objects.filter(email__endswith=".demo@example.test").count(),
            Candidatura.objects.filter(referencia_externa__startswith="DEMO-").count(),
            Prazo.objects.filter(codigo_regra="DEMO-PRAZO-URGENTE").count(),
        )
        first_notices = Notificacao.objects.count()
        call_command("carregar_cenario_demonstracao", stdout=output)

        self.assertEqual(first_counts, (4, 2, 1))
        self.assertEqual(
            (
                Utilizador.objects.filter(email__endswith=".demo@example.test").count(),
                Candidatura.objects.filter(referencia_externa__startswith="DEMO-").count(),
                Prazo.objects.filter(codigo_regra="DEMO-PRAZO-URGENTE").count(),
            ),
            first_counts,
        )
        self.assertEqual(Notificacao.objects.count(), first_notices)
        business = Candidatura.objects.get(referencia_externa="DEMO-EMP-001")
        individual = Candidatura.objects.get(referencia_externa="DEMO-IND-001")
        self.assertEqual(business.resultado_decisao, Candidatura.ResultadoDecisao.DEFERIDA_PARCIAL)
        self.assertEqual(
            set(business.transicoes.values_list("codigo", flat=True)),
            {"TR-001", "TR-002", "TR-004", "TR-006", "TR-007", "TR-008", "TR-009"},
        )
        self.assertTrue(
            business.beneficiarios.filter(
                resultado=BeneficiarioCandidatura.Resultado.INDEFERIDA
            ).exists()
        )
        self.assertTrue(
            SuspensaoPrazo.objects.filter(
                prazo__candidatura=business,
                fim_em__isnull=False,
            ).exists()
        )
        self.assertEqual(individual.estado_atual, Candidatura.Estado.ENCERRADA)
        self.assertTrue(individual.transicoes.filter(codigo="TR-021").exists())
        self.assertGreaterEqual(
            MovimentoFinanceiro.objects.filter(
                apoio__beneficiario__candidatura=individual,
                estado=MovimentoFinanceiro.Estado.CONFIRMADO,
            ).count(),
            1,
        )
        self.assertNotIn("Demonstracao!2026Segura", output.getvalue())
