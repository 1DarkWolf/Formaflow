from django.db.models import Q

from apps.candidaturas.models import Candidatura
from apps.candidaturas.selectors import (
    candidaturas_visiveis_por,
    utilizador_pode_consultar_equipa,
    utilizador_pode_operar_candidatura,
)

from .models import PedidoElementos, Tarefa, TransicaoCandidatura


def transicoes_visiveis_por(user, candidature):
    if not candidaturas_visiveis_por(user).filter(pk=candidature.pk).exists():
        return TransicaoCandidatura.objects.none()
    if utilizador_pode_consultar_equipa(user, candidature):
        return TransicaoCandidatura.objects.filter(candidatura=candidature)
    profile = getattr(user, "perfil_candidato", None)
    if not profile:
        return TransicaoCandidatura.objects.none()
    return TransicaoCandidatura.objects.filter(candidatura=candidature).filter(
        Q(beneficiario__isnull=True) | Q(beneficiario__candidato=profile)
    )


def pedidos_visiveis_por(user, candidature):
    if not candidaturas_visiveis_por(user).filter(pk=candidature.pk).exists():
        return PedidoElementos.objects.none()
    queryset = PedidoElementos.objects.filter(candidatura=candidature)
    if utilizador_pode_consultar_equipa(user, candidature):
        return queryset
    profile = getattr(user, "perfil_candidato", None)
    if not profile:
        return queryset.none()
    if (
        candidature.tipo == Candidatura.Tipo.INDIVIDUAL
        and candidature.titular_candidato_id == profile.pk
    ):
        return queryset
    return queryset.filter(questoes__beneficiario__candidato=profile).distinct()


def tarefas_visiveis_por(user, candidature):
    if not candidaturas_visiveis_por(user).filter(pk=candidature.pk).exists():
        return Tarefa.objects.none()
    queryset = Tarefa.objects.filter(candidatura=candidature)
    if utilizador_pode_consultar_equipa(user, candidature):
        return queryset
    return queryset.filter(atribuida_a=user)


def utilizador_pode_responder_questao(user, question):
    candidature = question.pedido.candidatura
    if utilizador_pode_operar_candidatura(user, candidature):
        return True
    profile = getattr(user, "perfil_candidato", None)
    return bool(
        profile and question.beneficiario_id and question.beneficiario.candidato_id == profile.pk
    )


PROXIMA_ACAO = {
    Candidatura.Estado.RASCUNHO: "Completar dados e documentos da preparação",
    Candidatura.Estado.PRONTA_SUBMISSAO: "Submeter no Iefponline e registar a referência",
    Candidatura.Estado.SUBMETIDA: "Confirmar receção ou início da análise",
    Candidatura.Estado.EM_ANALISE: "Acompanhar notificações do IEFP",
    Candidatura.Estado.AGUARDA_ELEMENTOS: "Responder às questões e anexar documentos",
    Candidatura.Estado.APROVADA_AGUARDA_TERMO: "Assinar e devolver o termo de aceitação",
    Candidatura.Estado.APROVADA_ACOMPANHAMENTO: "Acompanhar a formação",
    Candidatura.Estado.ENCERRAMENTO_PREPARACAO: "Reunir os documentos finais",
    Candidatura.Estado.ENCERRAMENTO_SUBMETIDO: "Confirmar o início da análise",
    Candidatura.Estado.ENCERRAMENTO_ANALISE: "Acompanhar a decisão de encerramento",
    Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO: "Confirmar pagamento ou regularização",
}


def proxima_acao(candidature):
    return PROXIMA_ACAO.get(candidature.estado_atual, "Consultar resultado e histórico")
