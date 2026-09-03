import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notificacao

logger = logging.getLogger(__name__)


def disponibilizar_notificacao(notification):
    now = timezone.now()
    Notificacao.objects.filter(pk=notification.pk).update(
        estado=Notificacao.Estado.ENVIADA,
        enviada_em=now,
        atualizado_em=now,
    )
    notification.estado = Notificacao.Estado.ENVIADA
    notification.enviada_em = now
    if settings.NOTIFICATION_EMAIL_ENABLED:
        transaction.on_commit(lambda: _enviar_email(notification.pk))
    return notification


def _enviar_email(notification_id):
    notification = Notificacao.objects.select_related("destinatario").get(pk=notification_id)
    try:
        send_mail(
            subject=f"Forma Flow — {notification.titulo}",
            message=(
                "Existe uma atualização no seu espaço Forma Flow. "
                "Inicie sessão para consultar os detalhes em segurança."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.destinatario.email],
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001
        logger.error("Falhou o envio opcional da notificação %s.", notification.pk)
        Notificacao.objects.filter(pk=notification.pk).update(
            estado=Notificacao.Estado.FALHOU,
            atualizado_em=timezone.now(),
        )


def marcar_notificacao_lida(*, notificacao_id, utilizador):
    notification = Notificacao.objects.filter(pk=notificacao_id).first()
    if not notification or notification.destinatario_id != utilizador.pk:
        raise PermissionDenied("Não pode alterar esta notificação.")
    if notification.estado != Notificacao.Estado.RESOLVIDA:
        now = timezone.now()
        Notificacao.objects.filter(pk=notification.pk).update(
            estado=Notificacao.Estado.LIDA,
            lida_em=notification.lida_em or now,
            atualizado_em=now,
        )
        notification.estado = Notificacao.Estado.LIDA
        notification.lida_em = notification.lida_em or now
    return notification


def resolver_notificacao(*, notificacao_id, utilizador):
    notification = Notificacao.objects.filter(pk=notificacao_id).first()
    if not notification or notification.destinatario_id != utilizador.pk:
        raise PermissionDenied("Não pode alterar esta notificação.")
    now = timezone.now()
    Notificacao.objects.filter(pk=notification.pk).update(
        estado=Notificacao.Estado.RESOLVIDA,
        lida_em=notification.lida_em or now,
        resolvida_em=notification.resolvida_em or now,
        atualizado_em=now,
    )
    notification.estado = Notificacao.Estado.RESOLVIDA
    return notification
