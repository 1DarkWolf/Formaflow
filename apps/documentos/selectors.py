from django.db.models import Q

from apps.candidaturas.models import Candidatura
from apps.candidaturas.selectors import (
    beneficiarios_visiveis_por,
    candidaturas_visiveis_por,
    utilizador_pode_consultar_equipa,
)
from apps.contas.models import PerfilCandidato

from .models import Documento, RequisitoDocumento


def _ambito_documental(user, candidatura):
    if utilizador_pode_consultar_equipa(user, candidatura):
        return Q()
    try:
        profile = user.perfil_candidato
    except PerfilCandidato.DoesNotExist:
        return Q(pk__in=[])
    own_beneficiaries = beneficiarios_visiveis_por(user, candidatura).values("pk")
    scope = Q(beneficiario_id__in=own_beneficiaries)
    if (
        candidatura.tipo == Candidatura.Tipo.INDIVIDUAL
        and candidatura.titular_candidato_id == profile.pk
    ):
        scope |= Q(beneficiario__isnull=True, participacao__isnull=True)
    return scope


def requisitos_visiveis_por(user, candidatura):
    if not candidaturas_visiveis_por(user).filter(pk=candidatura.pk).exists():
        return RequisitoDocumento.objects.none()
    return RequisitoDocumento.objects.filter(candidatura=candidatura).filter(
        _ambito_documental(user, candidatura)
    )


def documentos_visiveis_por(user, candidatura):
    if not candidaturas_visiveis_por(user).filter(pk=candidatura.pk).exists():
        return Documento.objects.none()
    return Documento.objects.filter(candidatura=candidatura).filter(
        _ambito_documental(user, candidatura)
    )
