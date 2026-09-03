from apps.candidaturas.models import Candidatura
from apps.candidaturas.selectors import (
    candidaturas_visiveis_por,
    utilizador_pode_consultar_equipa,
)

from .models import ApoioFinanceiro, MovimentoFinanceiro, Restituicao


def _apoios_no_ambito(utilizador, candidatura):
    if not candidaturas_visiveis_por(utilizador).filter(pk=candidatura.pk).exists():
        return ApoioFinanceiro.objects.none()
    queryset = ApoioFinanceiro.objects.filter(beneficiario__candidatura=candidatura)
    if utilizador_pode_consultar_equipa(utilizador, candidatura):
        return queryset
    profile = getattr(utilizador, "perfil_candidato", None)
    if not profile:
        return queryset.none()
    return queryset.filter(beneficiario__candidato=profile)


def apoios_visiveis_por(utilizador, candidatura):
    return _apoios_no_ambito(utilizador, candidatura).select_related(
        "beneficiario__candidato__utilizador", "participacao__acao_formacao"
    )


def movimentos_visiveis_por(utilizador, candidatura):
    return MovimentoFinanceiro.objects.filter(
        apoio__in=_apoios_no_ambito(utilizador, candidatura)
    ).select_related("apoio__beneficiario")


def restituicoes_visiveis_por(utilizador, candidatura):
    if not candidaturas_visiveis_por(utilizador).filter(pk=candidatura.pk).exists():
        return Restituicao.objects.none()
    queryset = Restituicao.objects.filter(candidatura=candidatura)
    if utilizador_pode_consultar_equipa(utilizador, candidatura):
        return queryset
    profile = getattr(utilizador, "perfil_candidato", None)
    if not profile:
        return queryset.none()
    if (
        candidatura.tipo == Candidatura.Tipo.INDIVIDUAL
        and candidatura.titular_candidato_id == profile.pk
    ):
        return queryset
    return queryset.filter(beneficiario__candidato=profile)
