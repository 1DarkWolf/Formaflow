from django.db.models import Q
from django.utils import timezone

from apps.contas.constants import GRUPO_ADMINISTRADOR
from apps.contas.models import PerfilCandidato

from .models import AssociacaoEmpresa, Empresa, VinculoLaboral


def utilizador_e_administrador(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.groups.filter(name=GRUPO_ADMINISTRADOR).exists())
    )


def empresas_visiveis_por(user, *, no_momento=None):
    if not user or not user.is_authenticated or not user.is_active:
        return Empresa.objects.none()
    if utilizador_e_administrador(user):
        return Empresa.objects.all()

    moment = no_momento or timezone.now()
    association_company_ids = (
        AssociacaoEmpresa.objects.vigentes(moment).filter(utilizador=user).values("empresa_id")
    )

    try:
        candidate_profile = user.perfil_candidato
    except PerfilCandidato.DoesNotExist:
        candidate_company_ids = Empresa.objects.none().values("id")
    else:
        reference_date = moment.date()
        candidate_company_ids = (
            VinculoLaboral.objects.filter(
                candidato=candidate_profile,
                empresa__isnull=False,
                inicio_em__lte=reference_date,
            )
            .filter(Q(fim_em__isnull=True) | Q(fim_em__gte=reference_date))
            .values("empresa_id")
        )

    return Empresa.objects.filter(
        Q(id__in=association_company_ids) | Q(id__in=candidate_company_ids)
    ).distinct()


def utilizador_pode_consultar_detalhes(user, empresa, *, no_momento=None):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if utilizador_e_administrador(user):
        return True
    moment = no_momento or timezone.now()
    return (
        AssociacaoEmpresa.objects.vigentes(moment)
        .filter(
            utilizador=user,
            empresa=empresa,
        )
        .exists()
    )


def utilizador_pode_gerir_empresa(user, empresa, *, no_momento=None):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if utilizador_e_administrador(user):
        return True
    moment = no_momento or timezone.now()
    return (
        AssociacaoEmpresa.objects.vigentes(moment)
        .filter(
            utilizador=user,
            empresa=empresa,
            papel__in=(
                AssociacaoEmpresa.Papel.GESTOR,
                AssociacaoEmpresa.Papel.RECURSOS_HUMANOS,
            ),
        )
        .exists()
    )
