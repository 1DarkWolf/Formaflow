import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import TentativaAutenticacao, Utilizador


def _chave_tentativa(request, identifier):
    normalized = Utilizador.objects.normalizar_email(str(identifier or ""))[:254]
    address = request.META.get("REMOTE_ADDR", "") if request else ""
    material = f"{normalized}|{address}".encode()
    return hmac.new(settings.DATA_HASH_KEY.encode(), material, hashlib.sha256).hexdigest()


def autenticacao_bloqueada(*, request, identifier, agora=None):
    moment = agora or timezone.now()
    attempt = TentativaAutenticacao.objects.filter(
        chave=_chave_tentativa(request, identifier)
    ).first()
    return bool(attempt and attempt.bloqueado_ate and attempt.bloqueado_ate > moment)


@transaction.atomic
def registar_falha_autenticacao(*, request, identifier, agora=None):
    moment = agora or timezone.now()
    key = _chave_tentativa(request, identifier)
    attempt, _created = TentativaAutenticacao.objects.select_for_update().get_or_create(
        chave=key,
        defaults={"janela_iniciada_em": moment},
    )
    window = timedelta(seconds=settings.LOGIN_ATTEMPT_WINDOW_SECONDS)
    if moment - attempt.janela_iniciada_em >= window:
        attempt.falhas = 0
        attempt.janela_iniciada_em = moment
        attempt.bloqueado_ate = None
    attempt.falhas += 1
    if attempt.falhas >= settings.LOGIN_MAX_ATTEMPTS:
        attempt.bloqueado_ate = moment + timedelta(seconds=settings.LOGIN_LOCK_SECONDS)
    attempt.save()
    return attempt


def limpar_falhas_autenticacao(*, request, identifier):
    TentativaAutenticacao.objects.filter(chave=_chave_tentativa(request, identifier)).delete()
