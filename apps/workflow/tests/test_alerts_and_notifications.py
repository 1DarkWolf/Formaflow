from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.documentos.tests.factories import DocumentFixtureMixin

from ..alerts import processar_alertas
from ..models import Notificacao, Prazo, Tarefa
from ..notifications import marcar_notificacao_lida


class AlertAndNotificationTests(DocumentFixtureMixin, TestCase):
    def make_deadline(self, *, days=2, unit=Prazo.Unidade.DIAS_CONSECUTIVOS):
        now = timezone.now()
        return Prazo.objects.create(
            candidatura=self.application,
            tipo=Prazo.Tipo.OUTRO,
            codigo_regra="TESTE-ALERTA",
            conjunto_regras=self.rules,
            inicio_em=now - timedelta(days=1),
            unidade=unit,
            duracao=max(days + 1, 1),
            limite_calculado=now + timedelta(days=days),
        )

    def test_processing_twice_does_not_duplicate_threshold_notifications(self):
        self.make_deadline(days=2)

        first = processar_alertas()
        total_after_first = Notificacao.objects.filter(codigo="PRAZO_PROXIMO").count()
        second = processar_alertas()

        self.assertGreater(first["notificacoes"], 0)
        self.assertEqual(second["notificacoes"], 0)
        self.assertGreater(
            Notificacao.objects.filter(codigo="PRAZO_PROXIMO").values("limiar").distinct().count(),
            1,
        )
        self.assertEqual(
            Notificacao.objects.filter(codigo="PRAZO_PROXIMO").count(),
            total_after_first,
        )

    def test_overdue_deadline_creates_one_urgent_task_and_safe_notice(self):
        self.make_deadline(days=-1)

        processar_alertas()
        processar_alertas()

        task = Tarefa.objects.get(tipo="REGULARIZAR_PRAZO_VENCIDO")
        notice = Notificacao.objects.get(codigo="PRAZO_VENCIDO")
        self.assertEqual(task.prioridade, Tarefa.Prioridade.CRITICA)
        self.assertEqual(notice.prioridade, Notificacao.Prioridade.URGENTE)
        self.assertNotIn(self.candidate.nif, notice.mensagem)
        self.assertEqual(Tarefa.objects.filter(tipo="REGULARIZAR_PRAZO_VENCIDO").count(), 1)

    def test_management_command_can_be_repeated(self):
        self.make_deadline(days=1)

        call_command("processar_alertas")
        count = Notificacao.objects.filter(codigo="PRAZO_PROXIMO").count()
        call_command("processar_alertas")

        self.assertEqual(Notificacao.objects.filter(codigo="PRAZO_PROXIMO").count(), count)

    def test_marking_notice_read_does_not_complete_linked_task(self):
        task = Tarefa.objects.create(
            candidatura=self.application,
            atribuida_a=self.manager,
            tipo="TESTE",
            titulo="Tratar processo",
        )
        notice = Notificacao.objects.create(
            destinatario=self.manager,
            candidatura=self.application,
            tarefa=task,
            codigo="TESTE",
            titulo="Aviso",
            mensagem="Consulte o processo.",
            estado=Notificacao.Estado.ENVIADA,
            chave_deduplicacao="teste-leitura",
        )

        marcar_notificacao_lida(notificacao_id=notice.pk, utilizador=self.manager)
        task.refresh_from_db()
        notice.refresh_from_db()

        self.assertEqual(notice.estado, Notificacao.Estado.LIDA)
        self.assertEqual(task.estado, Tarefa.Estado.ABERTA)

    def test_user_cannot_mark_another_users_notice(self):
        notice = Notificacao.objects.create(
            destinatario=self.manager,
            codigo="PRIVADO",
            titulo="Aviso privado",
            mensagem="Consulte o processo.",
            chave_deduplicacao="privado",
        )

        with self.assertRaises(PermissionDenied):
            marcar_notificacao_lida(notificacao_id=notice.pk, utilizador=self.outsider)

    @override_settings(NOTIFICATION_EMAIL_ENABLED=True)
    @patch("apps.workflow.notifications.send_mail", side_effect=RuntimeError("SMTP indisponível"))
    def test_optional_email_failure_does_not_roll_back_alert(self, _send_mail):
        self.make_deadline(days=1)

        with self.captureOnCommitCallbacks(execute=True):
            processar_alertas()

        notice = Notificacao.objects.get(codigo="PRAZO_PROXIMO", limiar="1")
        self.assertEqual(notice.estado, Notificacao.Estado.FALHOU)
        self.assertTrue(Prazo.objects.filter(candidatura=self.application).exists())

    def test_notification_page_is_scoped_to_recipient(self):
        notice = Notificacao.objects.create(
            destinatario=self.manager,
            candidatura=self.application,
            codigo="PRIVADO",
            titulo="Só do gestor",
            mensagem="Consulte o processo.",
            estado=Notificacao.Estado.ENVIADA,
            chave_deduplicacao="pagina-privada",
        )
        self.client.force_login(self.outsider)

        page = self.client.get(reverse("workflow:notificacoes"))
        update = self.client.post(reverse("workflow:ler_notificacao", args=[notice.pk]))

        self.assertNotContains(page, "Só do gestor")
        self.assertEqual(update.status_code, 403)
