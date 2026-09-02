from datetime import date

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.contas.constants import GRUPO_ADMINISTRADOR

from .models import ConjuntoRegras


def utilizador_pode_publicar_regras(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (
            user.is_superuser or Group.objects.filter(name=GRUPO_ADMINISTRADOR, user=user).exists()
        )
    )


@transaction.atomic
def publicar_conjunto(conjunto_id, publicado_por):
    if not utilizador_pode_publicar_regras(publicado_por):
        raise PermissionDenied("Apenas administradores podem publicar regras.")

    conjunto = ConjuntoRegras.objects.select_for_update().get(pk=conjunto_id)
    if conjunto.estado != ConjuntoRegras.Estado.RASCUNHO or conjunto.publicado_em:
        raise ValidationError("Este conjunto já foi publicado.")

    conjunto.full_clean()
    for parametro in conjunto.parametros.all():
        parametro.full_clean()

    end = conjunto.vigente_ate or date.max
    overlap = (
        ConjuntoRegras.objects.exclude(pk=conjunto.pk)
        .exclude(estado__in=(ConjuntoRegras.Estado.RASCUNHO, ConjuntoRegras.Estado.ARQUIVADO))
        .filter(codigo=conjunto.codigo, vigente_desde__lte=end)
        .filter(Q(vigente_ate__isnull=True) | Q(vigente_ate__gte=conjunto.vigente_desde))
        .exists()
    )
    if overlap:
        raise ValidationError("A vigência sobrepõe outra versão publicada do mesmo conjunto.")

    now = timezone.now()
    ConjuntoRegras.objects.filter(pk=conjunto.pk).update(
        estado=ConjuntoRegras.Estado.ATIVO,
        publicado_em=now,
        publicado_por=publicado_por,
        atualizado_em=now,
    )
    conjunto.refresh_from_db()
    return conjunto


def conjunto_aplicavel(codigo, data_referencia):
    return (
        ConjuntoRegras.objects.exclude(
            estado__in=(ConjuntoRegras.Estado.RASCUNHO, ConjuntoRegras.Estado.ARQUIVADO)
        )
        .filter(
            codigo=codigo.strip().upper(),
            vigente_desde__lte=data_referencia,
        )
        .filter(Q(vigente_ate__isnull=True) | Q(vigente_ate__gte=data_referencia))
        .order_by("-versao")
        .first()
    )
