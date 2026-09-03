from datetime import timedelta

from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.utils import timezone

from apps.candidaturas.models import Candidatura
from apps.candidaturas.selectors import (
    candidaturas_operacionais_por,
    candidaturas_visiveis_por,
)
from apps.contas.constants import GRUPO_GESTOR
from apps.documentos.models import EstadoDocumento, RequisitoDocumento
from apps.organizacoes.selectors import empresas_geridas_por, utilizador_e_administrador
from apps.regras.models import ConjuntoRegras
from apps.workflow.models import Notificacao, Prazo, Tarefa
from apps.workflow.selectors import proxima_acao

ESTADOS_TERMINAIS = {
    Candidatura.Estado.ENCERRADA,
    Candidatura.Estado.INDEFERIDA,
    Candidatura.Estado.ARQUIVADA,
    Candidatura.Estado.DESISTIDA,
    Candidatura.Estado.EXTINTA,
    Candidatura.Estado.REVOGADA,
    Candidatura.Estado.RASCUNHO_ARQUIVADO,
}


def _classificar_ambito(user, moment):
    if utilizador_e_administrador(user):
        return "administrador", "Administrador", Candidatura.objects.all()
    operational = candidaturas_operacionais_por(user, no_momento=moment)
    if (
        user.groups.filter(name=GRUPO_GESTOR).exists()
        or empresas_geridas_por(user, no_momento=moment).exists()
        or operational.exists()
    ):
        return "gestor", "Gestão operacional", operational
    return "candidato", "Candidato", candidaturas_visiveis_por(user, no_momento=moment)


def _documentos_pendentes(user, role, candidature_ids):
    requirements = RequisitoDocumento.objects.filter(
        candidatura_id__in=candidature_ids,
        obrigatorio=True,
        estado__in=(EstadoDocumento.EM_FALTA, EstadoDocumento.INVALIDO),
    )
    if role != "candidato":
        return requirements
    profile = getattr(user, "perfil_candidato", None)
    if not profile:
        return requirements.filter(beneficiario__isnull=True, participacao__isnull=True)
    return requirements.filter(
        Q(beneficiario__isnull=True, participacao__isnull=True)
        | Q(beneficiario__candidato=profile)
        | Q(participacao__beneficiario__candidato=profile)
    ).distinct()


def construir_dashboard(user):
    moment = timezone.now()
    role, role_label, applications = _classificar_ambito(user, moment)
    application_ids = applications.values("pk")
    active_tasks = Tarefa.objects.filter(
        candidatura_id__in=application_ids,
        estado__in=(Tarefa.Estado.ABERTA, Tarefa.Estado.EM_EXECUCAO),
    )
    if role == "candidato":
        active_tasks = active_tasks.filter(atribuida_a=user)

    recent = list(
        applications.select_related(
            "titular_candidato__utilizador",
            "titular_empresa",
        )[:5]
    )
    for application in recent:
        application.proxima_acao_display = proxima_acao(application)

    state_labels = dict(Candidatura.Estado.choices)
    state_summary = [
        {
            "codigo": row["estado_atual"],
            "nome": state_labels[row["estado_atual"]],
            "total": row["total"],
        }
        for row in applications.values("estado_atual")
        .annotate(total=Count("pk"))
        .order_by("estado_atual")
    ]
    requirements = _documentos_pendentes(user, role, application_ids)
    context = {
        "papel_painel": role,
        "papel_designacao": role_label,
        "candidaturas_recentes": recent,
        "distribuicao_estados": state_summary,
        "indicadores": {
            "candidaturas": applications.count(),
            "em_curso": applications.exclude(estado_atual__in=ESTADOS_TERMINAIS).count(),
            "tarefas_abertas": active_tasks.count(),
            "tarefas_vencidas": active_tasks.filter(data_limite__lt=moment).count(),
            "documentos_pendentes": requirements.count(),
            "prazos_proximos": Prazo.objects.filter(
                candidatura_id__in=application_ids,
                estado=Prazo.Estado.ATIVO,
            )
            .filter(
                Q(
                    limite_oficial__isnull=False,
                    limite_oficial__gte=moment,
                    limite_oficial__lte=moment + timedelta(days=7),
                )
                | Q(
                    limite_oficial__isnull=True,
                    limite_calculado__gte=moment,
                    limite_calculado__lte=moment + timedelta(days=7),
                )
            )
            .count(),
            "avisos_nao_lidos": Notificacao.objects.filter(
                destinatario=user,
                estado__in=(
                    Notificacao.Estado.PENDENTE,
                    Notificacao.Estado.ENVIADA,
                    Notificacao.Estado.FALHOU,
                ),
            ).count(),
        },
        "tarefas_prioritarias": active_tasks.select_related("candidatura")
        .annotate(
            prioridade_ordem=Case(
                When(prioridade=Tarefa.Prioridade.CRITICA, then=Value(0)),
                When(prioridade=Tarefa.Prioridade.ALTA, then=Value(1)),
                When(prioridade=Tarefa.Prioridade.NORMAL, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        .order_by(F("data_limite").asc(nulls_last=True), "prioridade_ordem")[:5],
    }
    if role == "administrador":
        context["indicadores_admin"] = {
            "regras_rascunho": ConjuntoRegras.objects.filter(
                estado=ConjuntoRegras.Estado.RASCUNHO
            ).count(),
            "avisos_falhados": Notificacao.objects.filter(estado=Notificacao.Estado.FALHOU).count(),
        }
    elif role == "gestor":
        context["empresas_geridas"] = empresas_geridas_por(user, no_momento=moment).count()
    return context
