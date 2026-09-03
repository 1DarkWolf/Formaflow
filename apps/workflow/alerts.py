from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.organizacoes.models import AssociacaoEmpresa
from apps.regras.models import Feriado, ParametroRegra

from .models import Notificacao, Prazo, Tarefa
from .notifications import disponibilizar_notificacao

CODIGO_LIMIARES_UTEIS = "CFG-ALERTA-DIAS-UTEIS"
CODIGO_LIMIARES_CONSECUTIVOS = "CFG-ALERTA-DIAS-CONSECUTIVOS"
CODIGO_LIMIARES_ENCERRAMENTO = "CFG-ALERTA-ENCERRAMENTO"

LIMIARES_PADRAO = {
    CODIGO_LIMIARES_UTEIS: [5, 2, 0],
    CODIGO_LIMIARES_CONSECUTIVOS: [15, 7, 3, 1, 0],
    CODIGO_LIMIARES_ENCERRAMENTO: [30, 15, 7, 3, 1, 0],
}


def _dias_uteis_restantes(inicio, fim, feriados):
    if fim <= inicio:
        return 0 if fim == inicio else -1
    current = inicio + timedelta(days=1)
    total = 0
    while current <= fim:
        if current.weekday() < 5 and current not in feriados:
            total += 1
        current += timedelta(days=1)
    return total


def _codigo_limiares(deadline):
    if deadline.tipo == Prazo.Tipo.ENCERRAMENTO:
        return CODIGO_LIMIARES_ENCERRAMENTO
    if deadline.unidade == Prazo.Unidade.DIAS_UTEIS:
        return CODIGO_LIMIARES_UTEIS
    return CODIGO_LIMIARES_CONSECUTIVOS


def _limiares_por_conjunto(deadlines):
    set_ids = {deadline.conjunto_regras_id for deadline in deadlines}
    rows = ParametroRegra.objects.filter(
        conjunto_regras_id__in=set_ids,
        codigo__in=LIMIARES_PADRAO,
    ).values_list("conjunto_regras_id", "codigo", "valor")
    configured = {}
    for set_id, code, value in rows:
        if isinstance(value, list) and all(isinstance(item, int) and item >= 0 for item in value):
            configured[(set_id, code)] = sorted(set(value), reverse=True)
    return configured


def _destinatarios(deadline, moment):
    candidature = deadline.candidatura
    if deadline.beneficiario_id:
        return {deadline.beneficiario.candidato.utilizador_id}
    recipients = set(
        candidature.atribuicoes.filter(ativa=True, inicio_em__lte=moment)
        .filter(Q(fim_em__isnull=True) | Q(fim_em__gte=moment))
        .values_list("utilizador_id", flat=True)
    )
    if candidature.titular_candidato_id:
        recipients.add(candidature.titular_candidato.utilizador_id)
    if candidature.titular_empresa_id:
        recipients.update(
            AssociacaoEmpresa.objects.vigentes(moment)
            .filter(
                empresa_id=candidature.titular_empresa_id,
                papel__in=(
                    AssociacaoEmpresa.Papel.GESTOR,
                    AssociacaoEmpresa.Papel.RECURSOS_HUMANOS,
                ),
            )
            .values_list("utilizador_id", flat=True)
        )
    return recipients


def _responsavel(deadline, recipients, moment):
    if deadline.beneficiario_id:
        return deadline.beneficiario.candidato.utilizador_id
    principal = (
        deadline.candidatura.atribuicoes.filter(ativa=True, principal=True, inicio_em__lte=moment)
        .filter(Q(fim_em__isnull=True) | Q(fim_em__gte=moment))
        .values_list("utilizador_id", flat=True)
        .first()
    )
    if principal:
        return principal
    if deadline.candidatura.titular_candidato_id:
        return deadline.candidatura.titular_candidato.utilizador_id
    return min(recipients) if recipients else None


def _priority(remaining):
    if remaining <= 0:
        return Notificacao.Prioridade.URGENTE
    if remaining <= 2:
        return Notificacao.Prioridade.ATENCAO
    return Notificacao.Prioridade.INFORMATIVA


@transaction.atomic
def processar_alertas(*, agora=None):
    moment = agora or timezone.now()
    today = timezone.localtime(moment).date()
    deadlines = list(
        Prazo.objects.filter(estado=Prazo.Estado.ATIVO)
        .select_related(
            "candidatura__titular_candidato__utilizador",
            "candidatura__titular_empresa",
            "beneficiario__candidato__utilizador",
            "conjunto_regras",
        )
        .prefetch_related("candidatura__atribuicoes")
    )
    holidays = set(
        Feriado.objects.filter(ativo=True, ambito=Feriado.Ambito.NACIONAL).values_list(
            "data", flat=True
        )
    )
    configured = _limiares_por_conjunto(deadlines)
    result = {"prazos": len(deadlines), "notificacoes": 0, "tarefas": 0}

    for deadline in deadlines:
        limit = timezone.localtime(deadline.limite_efetivo).date()
        if deadline.unidade == Prazo.Unidade.DIAS_UTEIS:
            remaining = _dias_uteis_restantes(today, limit, holidays)
        else:
            remaining = (limit - today).days
        recipients = _destinatarios(deadline, moment)
        limit_key = deadline.limite_efetivo.isoformat()

        if remaining < 0:
            task, created = Tarefa.objects.get_or_create(
                chave_deduplicacao=f"prazo:{deadline.pk}:vencido:{limit_key}",
                estado__in=(Tarefa.Estado.ABERTA, Tarefa.Estado.EM_EXECUCAO),
                defaults={
                    "candidatura": deadline.candidatura,
                    "beneficiario": deadline.beneficiario,
                    "atribuida_a_id": _responsavel(deadline, recipients, moment),
                    "tipo": "REGULARIZAR_PRAZO_VENCIDO",
                    "titulo": "Regularizar prazo vencido",
                    "descricao": "Consulte o processo e registe a ação adequada.",
                    "prioridade": Tarefa.Prioridade.CRITICA,
                    "data_limite": deadline.limite_efetivo,
                    "prazo_origem": deadline,
                },
            )
            result["tarefas"] += int(created)
            thresholds = ["VENCIDO"]
        else:
            code = _codigo_limiares(deadline)
            thresholds = [
                str(threshold)
                for threshold in configured.get(
                    (deadline.conjunto_regras_id, code), LIMIARES_PADRAO[code]
                )
                if remaining <= threshold
            ]
            task = None

        for threshold in thresholds:
            key = f"prazo:{deadline.pk}:limiar:{threshold}:limite:{limit_key}"
            for recipient_id in recipients:
                notification, created = Notificacao.objects.get_or_create(
                    destinatario_id=recipient_id,
                    chave_deduplicacao=key,
                    defaults={
                        "candidatura": deadline.candidatura,
                        "tarefa": task,
                        "prazo": deadline,
                        "codigo": "PRAZO_VENCIDO" if threshold == "VENCIDO" else "PRAZO_PROXIMO",
                        "titulo": (
                            "Prazo vencido" if threshold == "VENCIDO" else "Prazo a aproximar-se"
                        ),
                        "mensagem": "Consulte o processo e a próxima ação no Forma Flow.",
                        "prioridade": (
                            Notificacao.Prioridade.URGENTE
                            if threshold == "VENCIDO"
                            else _priority(remaining)
                        ),
                        "limiar": threshold,
                    },
                )
                if created:
                    disponibilizar_notificacao(notification)
                    result["notificacoes"] += 1
    return result
