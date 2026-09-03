from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.candidaturas.models import (
    BeneficiarioCandidatura,
    Candidatura,
    VerificacaoElegibilidade,
)
from apps.candidaturas.selectors import (
    utilizador_pode_consultar_equipa,
    utilizador_pode_operar_candidatura,
)
from apps.documentos.models import EstadoDocumento, SnapshotSubmissao
from apps.documentos.services import criar_snapshot
from apps.organizacoes.selectors import utilizador_e_administrador
from apps.regras.calendar import adicionar_dias_uteis
from apps.regras.models import ParametroRegra

from .exceptions import ConflitoWorkflow, TransicaoInvalida
from .models import (
    Notificacao,
    PedidoElementos,
    Prazo,
    QuestaoPedido,
    RespostaQuestao,
    SuspensaoPrazo,
    Tarefa,
    TermoAceitacao,
    TransicaoCandidatura,
)
from .selectors import utilizador_pode_responder_questao
from .transitions import obter_transicao

CODIGO_PRAZO_DECISAO = "CFG-ANALISE-PRAZO"
CODIGO_PRAZO_ELEMENTOS = "CFG-ELEMENTOS-PRAZO"
CODIGO_PRAZO_TERMO = "CFG-ACEITACAO-PRAZO"


def _normalizar_chave(value):
    key = str(value or "").strip()
    if not key or len(key) > 100:
        raise ValidationError("Indique uma chave de idempotência válida.")
    return key


def _obter_repetida(candidature, code, key):
    existing = TransicaoCandidatura.objects.filter(
        candidatura=candidature,
        chave_idempotencia=key,
    ).first()
    if existing and existing.codigo != code:
        raise ValidationError("A chave de idempotência já foi usada noutra operação.")
    return existing


def _pode_registar_acontecimento_oficial(user, candidature):
    return bool(
        utilizador_pode_operar_candidatura(user, candidature)
        and (
            utilizador_e_administrador(user) or utilizador_pode_consultar_equipa(user, candidature)
        )
    )


def _validar_permissao(user, candidature, permission):
    if permission in {"preparacao", "submissao", "resposta"}:
        allowed = utilizador_pode_operar_candidatura(user, candidature)
    elif permission == "oficial":
        allowed = _pode_registar_acontecimento_oficial(user, candidature)
    else:
        allowed = False
    if not allowed:
        raise PermissionDenied("Não pode registar este acontecimento na candidatura.")


def _validar_transicao(
    *,
    candidature,
    code,
    user,
    expected_version,
    confirmation,
    reason,
):
    definition = obter_transicao(code)
    if not definition:
        raise TransicaoInvalida("A transição indicada não existe.")
    if candidature.versao != expected_version:
        raise ConflitoWorkflow(
            "A candidatura foi alterada noutra sessão. Atualize a página e tente novamente."
        )
    if candidature.estado_atual not in definition.origens:
        raise TransicaoInvalida(
            f"{definition.codigo} não é permitida a partir de "
            f"{candidature.get_estado_atual_display()}."
        )
    _validar_permissao(user, candidature, definition.permissao)
    if definition.exige_confirmacao and not confirmation:
        raise ValidationError("Confirme expressamente o acontecimento antes de continuar.")
    if definition.exige_motivo and not reason.strip():
        raise ValidationError("Esta operação exige um motivo.")
    return definition


def _criar_transicao(
    *,
    candidature,
    definition,
    user,
    effective_at,
    origin,
    key,
    external_reference="",
    reason="",
    evidence=None,
):
    if not effective_at:
        raise ValidationError("Indique a data efetiva do acontecimento.")
    if timezone.is_naive(effective_at):
        effective_at = timezone.make_aware(effective_at)
    latest = candidature.transicoes.order_by("-efetiva_em", "-pk").first()
    if latest and effective_at < latest.efetiva_em:
        raise ValidationError(
            "A data efetiva não pode anteceder o último acontecimento da candidatura."
        )
    transition = TransicaoCandidatura(
        candidatura=candidature,
        codigo=definition.codigo,
        estado_anterior=candidature.estado_atual,
        estado_novo=definition.destino,
        efetiva_em=effective_at,
        ator=user,
        origem=origin,
        referencia_externa=external_reference.strip(),
        motivo=reason.strip(),
        evidencia=evidence,
        conjunto_regras=candidature.conjunto_regras,
        versao_anterior=candidature.versao,
        versao_nova=candidature.versao + 1,
        chave_idempotencia=key,
    )
    transition.full_clean()
    transition.save()
    return transition


def _atualizar_candidatura(
    candidature,
    transition,
    *,
    decision_result=None,
    submitted_at=None,
    external_reference=None,
):
    values = {
        "estado_atual": transition.estado_novo,
        "versao": transition.versao_nova,
        "atualizado_em": timezone.now(),
    }
    if decision_result is not None:
        values["resultado_decisao"] = decision_result
    if submitted_at is not None:
        values["submetida_em"] = submitted_at
    if external_reference:
        values["referencia_externa"] = external_reference.strip()
    if transition.codigo == "TR-004":
        values["idempotencia_submissao"] = transition.chave_idempotencia
    updated = Candidatura.objects.filter(
        pk=candidature.pk,
        versao=candidature.versao,
    ).update(**values)
    if updated != 1:
        raise ConflitoWorkflow(
            "A candidatura foi alterada noutra sessão. Atualize a página e tente novamente."
        )
    candidature.refresh_from_db()


def _validar_preparacao(candidature, warnings_acknowledged):
    if not warnings_acknowledged:
        raise ValidationError("Reconheça os avisos apresentados antes de validar.")
    if not candidature.beneficiarios.exists():
        raise ValidationError("A candidatura precisa de pelo menos um beneficiário.")
    without_training = candidature.beneficiarios.filter(participacoes_formacao__isnull=True)
    if without_training.exists():
        raise ValidationError("Associe pelo menos uma formação a cada beneficiário.")
    if not candidature.conta_pagamento_id:
        raise ValidationError("Defina a conta de pagamento antes de validar.")
    requirements = candidature.requisitos_documentais.all()
    if not requirements.exists():
        raise ValidationError("Gere e complete a checklist documental.")
    if (
        requirements.filter(obrigatorio=True, bloqueante=True)
        .exclude(estado__in=(EstadoDocumento.VALIDO, EstadoDocumento.DISPENSADO))
        .exists()
    ):
        raise ValidationError("Existem requisitos documentais bloqueantes por resolver.")
    if candidature.verificacoes_elegibilidade.filter(
        resultado=VerificacaoElegibilidade.Resultado.NAO_CONFORME
    ).exists():
        raise ValidationError("Resolva as verificações de elegibilidade não conformes.")


def _valor_inteiro(candidature, code):
    try:
        parameter = candidature.conjunto_regras.parametros.get(codigo=code)
    except ParametroRegra.DoesNotExist as error:
        raise ValidationError(f"O parâmetro {code} não está configurado.") from error
    value = parameter.valor
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"O parâmetro {code} é inválido.")
    return value


def _limite_dias_uteis(start, duration):
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
    local_start = timezone.localtime(start)
    limit_date = adicionar_dias_uteis(local_start.date(), duration)
    return datetime.combine(limit_date, local_start.timetz())


def _criar_prazo_dias_uteis(candidature, transition, *, type_code, rule_code):
    duration = _valor_inteiro(candidature, rule_code)
    deadline = _limite_dias_uteis(transition.efetiva_em, duration)
    deadline_record = Prazo(
        candidatura=candidature,
        tipo=type_code,
        codigo_regra=rule_code,
        conjunto_regras=candidature.conjunto_regras,
        inicio_em=transition.efetiva_em,
        unidade=Prazo.Unidade.DIAS_UTEIS,
        duracao=duration,
        limite_calculado=deadline,
        transicao_origem=transition,
    )
    deadline_record.full_clean()
    deadline_record.save()
    return deadline_record


def _destinatarios(candidature, actor):
    user_ids = {actor.pk} if actor else set()
    if candidature.titular_candidato_id:
        user_ids.add(candidature.titular_candidato.utilizador_id)
    user_ids.update(
        candidature.atribuicoes.filter(ativa=True).values_list("utilizador_id", flat=True)
    )
    user_ids.update(candidature.beneficiarios.values_list("candidato__utilizador_id", flat=True))
    return user_ids


def _notificar_estado(candidature, transition):
    for user_id in _destinatarios(candidature, transition.ator):
        Notificacao.objects.get_or_create(
            destinatario_id=user_id,
            chave_deduplicacao=f"transicao:{transition.pk}",
            defaults={
                "candidatura": candidature,
                "codigo": "ESTADO_CANDIDATURA",
                "titulo": f"Candidatura: {transition.get_estado_novo_display()}",
                "mensagem": "O acompanhamento da candidatura recebeu uma atualização de estado.",
                "prioridade": Notificacao.Prioridade.INFORMATIVA,
                "estado": Notificacao.Estado.ENVIADA,
                "enviada_em": timezone.now(),
            },
        )


def _criar_tarefa(
    candidature,
    *,
    key,
    type_code,
    title,
    assigned_to=None,
    beneficiary=None,
    deadline=None,
    priority=Tarefa.Prioridade.NORMAL,
    request=None,
    deadline_origin=None,
    term=None,
):
    active = Tarefa.objects.filter(
        chave_deduplicacao=key,
        estado__in=(Tarefa.Estado.ABERTA, Tarefa.Estado.EM_EXECUCAO),
    ).first()
    if active:
        return active
    task = Tarefa(
        candidatura=candidature,
        beneficiario=beneficiary,
        atribuida_a=assigned_to,
        tipo=type_code,
        titulo=title,
        estado=Tarefa.Estado.ABERTA,
        prioridade=priority,
        data_limite=deadline,
        pedido_origem=request,
        prazo_origem=deadline_origin,
        termo_origem=term,
        chave_deduplicacao=key,
    )
    task.full_clean()
    task.save()
    return task


def _notificar_tarefa(task):
    if not task.atribuida_a_id:
        return
    Notificacao.objects.get_or_create(
        destinatario_id=task.atribuida_a_id,
        chave_deduplicacao=f"tarefa:{task.pk}:inicial",
        defaults={
            "candidatura": task.candidatura,
            "tarefa": task,
            "codigo": "NOVA_TAREFA",
            "titulo": task.titulo,
            "mensagem": "Existe uma nova ação pendente no processo.",
            "prioridade": Notificacao.Prioridade.ATENCAO,
            "estado": Notificacao.Estado.ENVIADA,
            "enviada_em": timezone.now(),
        },
    )


def _concluir_tarefas(queryset, user, state=Tarefa.Estado.CONCLUIDA):
    values = {"estado": state, "atualizado_em": timezone.now()}
    if state == Tarefa.Estado.CONCLUIDA:
        values.update(concluida_em=timezone.now(), concluida_por=user)
    queryset.filter(estado__in=(Tarefa.Estado.ABERTA, Tarefa.Estado.EM_EXECUCAO)).update(**values)


def _cancelar_operacional(candidature, user, effective_at):
    _concluir_tarefas(candidature.tarefas.all(), user, Tarefa.Estado.CANCELADA)
    candidature.prazos.filter(estado__in=(Prazo.Estado.ATIVO, Prazo.Estado.SUSPENSO)).update(
        estado=Prazo.Estado.CANCELADO,
        atualizado_em=timezone.now(),
    )
    candidature.pedidos_elementos.filter(
        estado__in=(PedidoElementos.Estado.ABERTO, PedidoElementos.Estado.RESPOSTA_RASCUNHO)
    ).update(estado=PedidoElementos.Estado.CANCELADO, atualizado_em=timezone.now())
    SuspensaoPrazo.objects.filter(
        prazo__candidatura=candidature,
        fim_em__isnull=True,
    ).update(fim_em=effective_at)


@transaction.atomic
def registar_criacao(candidature, actor):
    key = f"criacao:{candidature.public_id}"
    existing = _obter_repetida(candidature, "TR-001", key)
    if existing:
        return existing
    transition = TransicaoCandidatura(
        candidatura=candidature,
        codigo="TR-001",
        estado_anterior=None,
        estado_novo=Candidatura.Estado.RASCUNHO,
        efetiva_em=candidature.criado_em,
        ator=actor,
        origem=TransicaoCandidatura.Origem.UTILIZADOR,
        conjunto_regras=candidature.conjunto_regras,
        versao_anterior=0,
        versao_nova=1,
        chave_idempotencia=key,
    )
    transition.full_clean()
    transition.save()
    return transition


@transaction.atomic
def aplicar_transicao(
    *,
    candidatura_id,
    codigo,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    origem=TransicaoCandidatura.Origem.UTILIZADOR,
    referencia_externa="",
    motivo="",
    evidencia=None,
    confirmacao=False,
    avisos_reconhecidos=False,
):
    code = str(codigo).strip().upper()
    key = _normalizar_chave(chave_idempotencia)
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related(
            "titular_candidato__utilizador",
            "titular_empresa",
            "conjunto_regras",
        )
        .get(pk=candidatura_id)
    )
    existing = _obter_repetida(candidature, code, key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code=code,
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason=motivo,
    )
    if definition.especializada:
        raise TransicaoInvalida("Esta transição exige o respetivo formulário especializado.")
    if code == "TR-002":
        _validar_preparacao(candidature, avisos_reconhecidos)
    if code == "TR-004" and origem != TransicaoCandidatura.Origem.IEFPONLINE:
        raise ValidationError("A submissão deve identificar o Iefponline como origem.")
    if code in {"TR-006", "TR-012"} and origem not in {
        TransicaoCandidatura.Origem.IEFPONLINE,
        TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
    }:
        raise ValidationError("Identifique a origem externa deste acontecimento.")
    if code == "TR-006" and not (referencia_externa.strip() or evidencia):
        raise ValidationError("Identifique o acontecimento externo por referência ou evidência.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=efetiva_em,
        origin=origem,
        key=key,
        external_reference=referencia_externa,
        reason=motivo,
        evidence=evidencia,
    )
    if code == "TR-004":
        criar_snapshot(
            candidatura_id=candidature.pk,
            utilizador=utilizador,
            finalidade=SnapshotSubmissao.Finalidade.SUBMISSAO,
            transicao=transition,
        )
        deadline = _criar_prazo_dias_uteis(
            candidature,
            transition,
            type_code=Prazo.Tipo.DECISAO,
            rule_code=CODIGO_PRAZO_DECISAO,
        )
        task = _criar_tarefa(
            candidature,
            key=f"candidatura:{candidature.pk}:acompanhar-analise",
            type_code="ACOMPANHAR_ANALISE",
            title="Acompanhar a análise externa",
            assigned_to=utilizador,
            deadline=deadline.limite_efetivo,
            deadline_origin=deadline,
        )
        _notificar_tarefa(task)
    if code in {"TR-005", "TR-012"}:
        _cancelar_operacional(candidature, utilizador, transition.efetiva_em)
    _atualizar_candidatura(
        candidature,
        transition,
        submitted_at=transition.efetiva_em if code == "TR-004" else None,
        external_reference=referencia_externa if code == "TR-004" else None,
    )
    _notificar_estado(candidature, transition)
    return transition


def _destinatario_da_questao(question, actor):
    if question.beneficiario_id:
        return question.beneficiario.candidato.utilizador
    candidature = question.pedido.candidatura
    if (
        question.destinatario == QuestaoPedido.Destinatario.TITULAR
        and candidature.titular_candidato_id
    ):
        return candidature.titular_candidato.utilizador
    principal = candidature.atribuicoes.filter(ativa=True, principal=True).first()
    return principal.utilizador if principal else actor


@transaction.atomic
def registar_pedido_elementos(
    *,
    candidatura_id,
    questoes,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    recebido_em,
    referencia_externa="",
    descricao="",
    evidencia=None,
    confirmacao=False,
):
    key = _normalizar_chave(chave_idempotencia)
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    existing = _obter_repetida(candidature, "TR-007", key)
    if existing:
        return existing, None
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-007",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    if not questoes:
        raise ValidationError("O pedido deve conter pelo menos uma questão.")
    if not (referencia_externa.strip() or evidencia):
        raise ValidationError("Identifique o pedido externo por referência ou evidência.")
    decision_deadline = (
        candidature.prazos.select_for_update()
        .filter(tipo=Prazo.Tipo.DECISAO, estado=Prazo.Estado.ATIVO)
        .order_by("-pk")
        .first()
    )
    if not decision_deadline:
        raise ValidationError("Não existe um prazo de decisão ativo para suspender.")
    if decision_deadline.suspensoes.filter(fim_em__isnull=True).exists():
        raise ValidationError("O prazo de decisão já se encontra suspenso.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=recebido_em,
        origin=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
        key=key,
        external_reference=referencia_externa,
        evidence=evidencia,
    )
    recebido_em = transition.efetiva_em
    duration = _valor_inteiro(candidature, CODIGO_PRAZO_ELEMENTOS)
    response_limit = _limite_dias_uteis(recebido_em, duration)
    request = PedidoElementos(
        candidatura=candidature,
        fase=PedidoElementos.Fase.ANALISE,
        referencia_externa=referencia_externa.strip(),
        recebido_em=recebido_em,
        data_limite=response_limit,
        descricao=descricao.strip(),
        evidencia=evidencia,
        registado_por=utilizador,
    )
    request.full_clean()
    request.save()
    created_questions = []
    for position, item in enumerate(questoes, start=1):
        question = QuestaoPedido(
            pedido=request,
            ordem=position,
            texto=str(item.get("texto", "")).strip(),
            destinatario=item.get("destinatario", QuestaoPedido.Destinatario.TITULAR),
            beneficiario=item.get("beneficiario"),
            exige_texto=item.get("exige_texto", True),
            exige_documento=item.get("exige_documento", False),
            tipo_documento_pedido=item.get("tipo_documento"),
            obrigatoria=item.get("obrigatoria", True),
        )
        question.full_clean()
        question.save()
        created_questions.append(question)
    response_deadline = Prazo(
        candidatura=candidature,
        tipo=Prazo.Tipo.RESPOSTA_ELEMENTOS,
        codigo_regra=CODIGO_PRAZO_ELEMENTOS,
        conjunto_regras=candidature.conjunto_regras,
        inicio_em=recebido_em,
        unidade=Prazo.Unidade.DIAS_UTEIS,
        duracao=duration,
        limite_calculado=response_limit,
        transicao_origem=transition,
    )
    response_deadline.full_clean()
    response_deadline.save()
    suspension = SuspensaoPrazo(
        prazo=decision_deadline,
        pedido_elementos=request,
        inicio_em=recebido_em,
        origem=SuspensaoPrazo.Origem.CALCULADA,
        motivo="Pedido de elementos adicionais registado.",
        registada_por=utilizador,
    )
    suspension.full_clean()
    suspension.save()
    Prazo.objects.filter(pk=decision_deadline.pk).update(
        estado=Prazo.Estado.SUSPENSO,
        atualizado_em=timezone.now(),
    )
    for question in created_questions:
        assigned_to = _destinatario_da_questao(question, utilizador)
        task = _criar_tarefa(
            candidature,
            key=f"pedido:{request.pk}:questao:{question.pk}",
            type_code="RESPONDER_ELEMENTOS",
            title=f"Responder à questão {question.ordem} do pedido",
            assigned_to=assigned_to,
            beneficiary=question.beneficiario,
            deadline=response_limit,
            priority=Tarefa.Prioridade.ALTA,
            request=request,
        )
        _notificar_tarefa(task)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition, request


@transaction.atomic
def guardar_resposta_rascunho(*, questao_id, utilizador, texto="", versoes_documentos=()):
    question = (
        QuestaoPedido.objects.select_for_update()
        .select_related(
            "pedido__candidatura__titular_empresa",
            "pedido__candidatura__titular_candidato",
            "beneficiario__candidato",
            "tipo_documento_pedido",
        )
        .get(pk=questao_id)
    )
    request = question.pedido
    if request.estado not in {
        PedidoElementos.Estado.ABERTO,
        PedidoElementos.Estado.RESPOSTA_RASCUNHO,
    }:
        raise ValidationError("Este pedido já não aceita respostas em rascunho.")
    if not utilizador_pode_responder_questao(utilizador, question):
        raise PermissionDenied("Não pode responder a esta questão.")
    versions = list(versoes_documentos)
    for version in versions:
        if version.documento.candidatura_id != request.candidatura_id:
            raise ValidationError("Um anexo não pertence à candidatura.")
        if (
            question.tipo_documento_pedido_id
            and version.documento.tipo_documento_id != question.tipo_documento_pedido_id
        ):
            raise ValidationError("O anexo não corresponde ao tipo documental pedido.")
    next_number = (question.respostas.aggregate(highest=Max("numero"))["highest"] or 0) + 1
    question.respostas.filter(estado=RespostaQuestao.Estado.RASCUNHO).update(
        estado=RespostaQuestao.Estado.SUBSTITUIDA
    )
    answer = RespostaQuestao.objects.create(
        questao=question,
        numero=next_number,
        texto=texto.strip(),
        estado=RespostaQuestao.Estado.RASCUNHO,
        autor=utilizador,
    )
    answer.versoes_documentos.set(versions)
    PedidoElementos.objects.filter(pk=request.pk).update(
        estado=PedidoElementos.Estado.RESPOSTA_RASCUNHO,
        atualizado_em=timezone.now(),
    )
    return answer


def _validar_resposta(question, answer):
    if not answer:
        raise ValidationError(f"A questão {question.ordem} ainda não tem resposta.")
    if question.exige_texto and not answer.texto.strip():
        raise ValidationError(f"A questão {question.ordem} exige resposta textual.")
    attachments = answer.versoes_documentos.select_related("documento")
    if question.exige_documento and not attachments.exists():
        raise ValidationError(f"A questão {question.ordem} exige um documento.")
    if (
        question.tipo_documento_pedido_id
        and attachments.exclude(
            documento__tipo_documento_id=question.tipo_documento_pedido_id
        ).exists()
    ):
        raise ValidationError(f"A questão {question.ordem} tem um documento do tipo incorreto.")


@transaction.atomic
def registar_resposta_completa(
    *,
    pedido_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    confirmacao=False,
):
    request = (
        PedidoElementos.objects.select_for_update()
        .select_related(
            "candidatura__titular_candidato__utilizador",
            "candidatura__titular_empresa",
            "candidatura__conjunto_regras",
        )
        .get(pk=pedido_id)
    )
    candidature = Candidatura.objects.select_for_update().get(pk=request.candidatura_id)
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-008", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-008",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    if request.estado not in {
        PedidoElementos.Estado.ABERTO,
        PedidoElementos.Estado.RESPOSTA_RASCUNHO,
    }:
        raise ValidationError("O pedido já não aguarda uma resposta completa.")
    if efetiva_em < request.recebido_em:
        raise ValidationError("A resposta não pode anteceder a receção do pedido.")
    selected_answers = []
    for question in request.questoes.order_by("ordem"):
        answer = (
            question.respostas.exclude(estado=RespostaQuestao.Estado.SUBSTITUIDA)
            .order_by("-numero")
            .first()
        )
        if question.obrigatoria or answer:
            _validar_resposta(question, answer)
        if answer:
            selected_answers.append(answer)
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=efetiva_em,
        origin=TransicaoCandidatura.Origem.IEFPONLINE,
        key=key,
    )
    efetiva_em = transition.efetiva_em
    now = timezone.now()
    for answer in selected_answers:
        answer.questao.respostas.filter(estado=RespostaQuestao.Estado.SUBMETIDA).update(
            estado=RespostaQuestao.Estado.SUBSTITUIDA
        )
        RespostaQuestao.objects.filter(pk=answer.pk).update(
            estado=RespostaQuestao.Estado.SUBMETIDA,
            submetida_em=efetiva_em,
        )
    PedidoElementos.objects.filter(pk=request.pk).update(
        estado=PedidoElementos.Estado.RESPONDIDO,
        atualizado_em=now,
    )
    response_deadline = (
        candidature.prazos.select_for_update()
        .filter(
            tipo=Prazo.Tipo.RESPOSTA_ELEMENTOS,
            inicio_em=request.recebido_em,
            limite_calculado=request.data_limite,
        )
        .first()
    )
    if response_deadline:
        Prazo.objects.filter(pk=response_deadline.pk).update(
            estado=Prazo.Estado.CUMPRIDO,
            atualizado_em=now,
        )
    suspension = SuspensaoPrazo.objects.select_for_update().get(
        pedido_elementos=request,
        fim_em__isnull=True,
    )
    decision_deadline = suspension.prazo
    extension = efetiva_em - suspension.inicio_em
    if extension.total_seconds() < 0:
        raise ValidationError("O fim da suspensão não pode anteceder o início.")
    SuspensaoPrazo.objects.filter(pk=suspension.pk).update(fim_em=efetiva_em)
    Prazo.objects.filter(pk=decision_deadline.pk).update(
        estado=Prazo.Estado.ATIVO,
        limite_calculado=decision_deadline.limite_calculado + extension,
        atualizado_em=now,
    )
    _concluir_tarefas(request.tarefas.all(), utilizador)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def registar_decisao(
    *,
    candidatura_id,
    resultados,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    evidencia,
    referencia_externa="",
    motivo="",
    motivos_beneficiarios=None,
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    normalized = {int(key): value for key, value in resultados.items()}
    beneficiaries = list(candidature.beneficiarios.select_for_update().order_by("pk"))
    if set(normalized) != {item.pk for item in beneficiaries}:
        raise ValidationError("Registe um resultado para todos os beneficiários.")
    allowed = {
        BeneficiarioCandidatura.Resultado.DEFERIDA,
        BeneficiarioCandidatura.Resultado.INDEFERIDA,
        BeneficiarioCandidatura.Resultado.ARQUIVADA,
    }
    if not set(normalized.values()).issubset(allowed):
        raise ValidationError("Existe um resultado individual inválido.")
    outcomes = list(normalized.values())
    if BeneficiarioCandidatura.Resultado.DEFERIDA in outcomes:
        code = "TR-009"
        global_result = (
            Candidatura.ResultadoDecisao.DEFERIDA_TOTAL
            if set(outcomes) == {BeneficiarioCandidatura.Resultado.DEFERIDA}
            else Candidatura.ResultadoDecisao.DEFERIDA_PARCIAL
        )
    elif set(outcomes) == {BeneficiarioCandidatura.Resultado.INDEFERIDA}:
        code = "TR-010"
        global_result = Candidatura.ResultadoDecisao.INDEFERIDA
    elif set(outcomes) == {BeneficiarioCandidatura.Resultado.ARQUIVADA}:
        code = "TR-011"
        global_result = Candidatura.ResultadoDecisao.ARQUIVADA
    else:
        raise ValidationError("Uma decisão sem deferimentos deve ser uniforme.")
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, code, key)
    if existing:
        return existing
    if not evidencia:
        raise ValidationError("Associe a comunicação que comprova a decisão oficial.")
    definition = _validar_transicao(
        candidature=candidature,
        code=code,
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason=motivo,
    )
    reasons = motivos_beneficiarios or {}
    for beneficiary in beneficiaries:
        outcome = normalized[beneficiary.pk]
        individual_reason = str(
            reasons.get(beneficiary.pk, reasons.get(str(beneficiary.pk), ""))
        ).strip()
        if outcome != BeneficiarioCandidatura.Resultado.DEFERIDA and not individual_reason:
            raise ValidationError(
                "Indique o motivo do resultado de "
                f"{beneficiary.candidato.utilizador.get_full_name()}."
            )
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=efetiva_em,
        origin=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
        key=key,
        external_reference=referencia_externa,
        reason=motivo,
        evidence=evidencia,
    )
    efetiva_em = transition.efetiva_em
    for beneficiary in beneficiaries:
        outcome = normalized[beneficiary.pk]
        BeneficiarioCandidatura.objects.filter(pk=beneficiary.pk).update(
            resultado=outcome,
            decidido_em=efetiva_em,
            motivo_decisao=str(
                reasons.get(beneficiary.pk, reasons.get(str(beneficiary.pk), ""))
            ).strip(),
            referencia_decisao=referencia_externa.strip(),
            atualizado_em=timezone.now(),
        )
    candidature.prazos.filter(
        tipo=Prazo.Tipo.DECISAO,
        estado__in=(Prazo.Estado.ATIVO, Prazo.Estado.SUSPENSO),
    ).update(estado=Prazo.Estado.CUMPRIDO, atualizado_em=timezone.now())
    _concluir_tarefas(candidature.tarefas.filter(tipo="ACOMPANHAR_ANALISE"), utilizador)
    if code == "TR-009":
        term_deadline = _criar_prazo_dias_uteis(
            candidature,
            transition,
            type_code=Prazo.Tipo.TERMO,
            rule_code=CODIGO_PRAZO_TERMO,
        )
        term = TermoAceitacao.objects.create(
            candidatura=candidature,
            estado=TermoAceitacao.Estado.PENDENTE,
            notificado_em=efetiva_em,
            data_limite=term_deadline.limite_calculado,
        )
        task = _criar_tarefa(
            candidature,
            key=f"candidatura:{candidature.pk}:termo",
            type_code="DEVOLVER_TERMO",
            title="Devolver o termo de aceitação",
            assigned_to=utilizador,
            deadline=term_deadline.limite_efetivo,
            term=term,
            priority=Tarefa.Prioridade.ALTA,
        )
        _notificar_tarefa(task)
    else:
        _cancelar_operacional(candidature, utilizador, efetiva_em)
    _atualizar_candidatura(
        candidature,
        transition,
        decision_result=global_result,
    )
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def corrigir_limite_prazo(*, prazo_id, utilizador, novo_limite, motivo):
    deadline = (
        Prazo.objects.select_for_update()
        .select_related("candidatura__titular_empresa", "candidatura__titular_candidato")
        .get(pk=prazo_id)
    )
    if not _pode_registar_acontecimento_oficial(utilizador, deadline.candidatura):
        raise PermissionDenied("Não pode corrigir este prazo.")
    reason = motivo.strip()
    if not reason:
        raise ValidationError("A correção do prazo exige um motivo.")
    if novo_limite and timezone.is_naive(novo_limite):
        novo_limite = timezone.make_aware(novo_limite)
    if not novo_limite or novo_limite < deadline.inicio_em:
        raise ValidationError("O novo limite não pode anteceder o início do prazo.")
    previous = deadline.limite_efetivo
    Prazo.objects.filter(pk=deadline.pk).update(
        limite_oficial=novo_limite,
        limite_anterior=previous,
        corrigido_por=utilizador,
        motivo_correcao=reason,
        atualizado_em=timezone.now(),
    )
    deadline.refresh_from_db()
    return deadline
