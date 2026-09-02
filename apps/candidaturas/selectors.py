from django.db.models import Q
from django.utils import timezone

from apps.contas.models import PerfilCandidato
from apps.organizacoes.models import AssociacaoEmpresa
from apps.organizacoes.selectors import (
    utilizador_e_administrador,
    utilizador_pode_gerir_empresa,
)

from .models import AtribuicaoCandidatura, BeneficiarioCandidatura, Candidatura


def _utilizador_ativo(user):
    return bool(user and user.is_authenticated and user.is_active)


def _atribuicoes_vigentes(no_momento):
    return AtribuicaoCandidatura.objects.filter(
        ativa=True,
        inicio_em__lte=no_momento,
    ).filter(Q(fim_em__isnull=True) | Q(fim_em__gte=no_momento))


def candidaturas_visiveis_por(user, *, no_momento=None):
    if not _utilizador_ativo(user):
        return Candidatura.objects.none()
    if utilizador_e_administrador(user):
        return Candidatura.objects.all()

    moment = no_momento or timezone.now()
    association_company_ids = (
        AssociacaoEmpresa.objects.vigentes(moment).filter(utilizador=user).values("empresa_id")
    )
    assignment_ids = _atribuicoes_vigentes(moment).filter(utilizador=user).values("candidatura_id")

    personal_scope = Q(pk__in=[])
    try:
        profile = user.perfil_candidato
    except PerfilCandidato.DoesNotExist:
        pass
    else:
        personal_scope = Q(titular_candidato=profile) | Q(beneficiarios__candidato=profile)

    return Candidatura.objects.filter(
        personal_scope
        | Q(titular_empresa_id__in=association_company_ids)
        | Q(id__in=assignment_ids)
    ).distinct()


def utilizador_pode_editar_candidatura(user, candidatura, *, no_momento=None):
    if not _utilizador_ativo(user) or not candidatura.editavel:
        return False
    if utilizador_e_administrador(user):
        return True
    if candidatura.tipo == Candidatura.Tipo.INDIVIDUAL:
        try:
            if candidatura.titular_candidato_id == user.perfil_candidato.pk:
                return True
        except PerfilCandidato.DoesNotExist:
            pass
    if candidatura.titular_empresa_id and utilizador_pode_gerir_empresa(
        user,
        candidatura.titular_empresa,
        no_momento=no_momento,
    ):
        return True
    moment = no_momento or timezone.now()
    return (
        _atribuicoes_vigentes(moment)
        .filter(
            candidatura=candidatura,
            utilizador=user,
            papel__in=(
                AtribuicaoCandidatura.Papel.RESPONSAVEL,
                AtribuicaoCandidatura.Papel.COLABORADOR,
            ),
        )
        .exists()
    )


def utilizador_pode_consultar_equipa(user, candidatura, *, no_momento=None):
    if not _utilizador_ativo(user):
        return False
    if utilizador_e_administrador(user):
        return True
    if candidatura.titular_empresa_id:
        moment = no_momento or timezone.now()
        if (
            AssociacaoEmpresa.objects.vigentes(moment)
            .filter(utilizador=user, empresa=candidatura.titular_empresa)
            .exists()
        ):
            return True
    moment = no_momento or timezone.now()
    return (
        _atribuicoes_vigentes(moment)
        .filter(
            candidatura=candidatura,
            utilizador=user,
        )
        .exists()
    )


def beneficiarios_visiveis_por(user, candidatura):
    queryset = BeneficiarioCandidatura.objects.filter(candidatura=candidatura)
    if utilizador_pode_consultar_equipa(user, candidatura):
        return queryset
    try:
        profile = user.perfil_candidato
    except PerfilCandidato.DoesNotExist:
        return queryset.none()
    return queryset.filter(candidato=profile)
