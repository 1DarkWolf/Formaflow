from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from apps.contas.models import Utilizador

from ..models import RegistoAuditoria
from ..services import registar_evento


class AuditTests(TestCase):
    def setUp(self):
        self.user = Utilizador.objects.create_user(
            email="auditoria@example.test",
            password="Segura!2026Projeto",
            nome_proprio="Ana",
            apelido="Auditoria",
        )

    def test_service_only_persists_whitelisted_metadata_and_hashes_ip(self):
        request = RequestFactory().get("/exportar", REMOTE_ADDR="192.0.2.10")

        event = registar_evento(
            acao="exportar_candidaturas_csv",
            tipo_objeto="Candidatura",
            utilizador=self.user,
            request=request,
            metadados={"formato": "CSV", "quantidade": 2, "nif": "123456789"},
        )

        self.assertEqual(event.acao, "EXPORTAR_CANDIDATURAS_CSV")
        self.assertEqual(event.metadados, {"formato": "CSV", "quantidade": 2})
        self.assertEqual(len(event.hash_ip), 64)
        self.assertNotIn("192.0.2.10", event.hash_ip)

    def test_audit_record_cannot_be_changed_or_deleted(self):
        event = registar_evento(
            acao="CONSULTAR",
            tipo_objeto="Candidatura",
            utilizador=self.user,
        )
        event.resultado = RegistoAuditoria.Resultado.ERRO

        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            RegistoAuditoria.objects.filter(pk=event.pk).delete()
