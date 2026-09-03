import calendar
from datetime import datetime, time

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.candidaturas.models import (
    BeneficiarioCandidatura,
    Candidatura,
    ParticipacaoFormacao,
    VerificacaoElegibilidade,
)
from apps.candidaturas.selectors import (
    utilizador_pode_consultar_equipa,
    utilizador_pode_operar_candidatura,
)
from apps.documentos.models import (
    EstadoDocumento,
    FaseDocumento,
    RequisitoDocumento,
    SnapshotSubmissao,
    VersaoDocumento,
)
from apps.documentos.services import criar_snapshot
from apps.formacoes.models import AcaoFormacao
from apps.organizacoes.selectors import utilizador_e_administrador
from apps.regras.calendar import adicionar_dias_uteis
from apps.regras.models import ParametroRegra, TipoDocumento

from .exceptions import ConflitoWorkflow, TransicaoInvalida
from .models import (
    Notificacao,
    PedidoElementos,
    PedidoEncerramento,
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
CODIGO_PRAZO_PRIMEIRA_PRESTACAO = "CFG-PRIMEIRA-PRESTACAO"
CODIGO_PRAZO_REMANESCENTE = "CFG-REMANESCENTE"
CODIGO_PRAZO_ENCERRAMENTO = "CFG-ENCERRAMENTO"


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
    elif permission == "administracao":
        allowed = utilizador_pode_operar_candidatura(
            user, candidature
        ) and utilizador_e_administrador(user)
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
    new_state=None,
    corrects=None,
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
        estado_novo=new_state or definition.destino,
        efetiva_em=effective_at,
        ator=user,
        origem=origin,
        referencia_externa=external_reference.strip(),
        motivo=reason.strip(),
        evidencia=evidence,
        corrige_transicao=corrects,
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
    requirement=None,
    closure=None,
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
        requisito_origem=requirement,
        encerramento_origem=closure,
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


def _limite_meses(start, duration):
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
    local_start = timezone.localtime(start)
    month_index = local_start.month - 1 + duration
    year = local_start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(local_start.day, calendar.monthrange(year, month)[1])
    return local_start.replace(year=year, month=month, day=day)


def _concluir_prazos(candidature, types):
    candidature.prazos.filter(
        tipo__in=types,
        estado__in=(Prazo.Estado.ATIVO, Prazo.Estado.SUSPENSO),
    ).update(estado=Prazo.Estado.CUMPRIDO, atualizado_em=timezone.now())


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
    if code in {"TR-006", "TR-012", "TR-014", "TR-017", "TR-022"} and origem not in {
        TransicaoCandidatura.Origem.IEFPONLINE,
        TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
    }:
        raise ValidationError("Identifique a origem externa deste acontecimento.")
    if code in {"TR-006", "TR-014", "TR-017", "TR-022"} and not (
        referencia_externa.strip() or evidencia
    ):
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
    if code == "TR-017":
        closure = candidature.pedido_encerramento
        PedidoEncerramento.objects.filter(pk=closure.pk).update(
            estado=PedidoEncerramento.Estado.EM_ANALISE,
            analise_iniciada_em=transition.efetiva_em,
            referencia_externa=referencia_externa.strip() or closure.referencia_externa,
            atualizado_em=timezone.now(),
        )
    if code == "TR-022":
        BeneficiarioCandidatura.objects.filter(
            candidatura=candidature,
            resultado=BeneficiarioCandidatura.Resultado.DEFERIDA,
        ).update(
            resultado=BeneficiarioCandidatura.Resultado.REVOGADA,
            decidido_em=transition.efetiva_em,
            motivo_decisao=motivo.strip(),
            referencia_decisao=referencia_externa.strip(),
            atualizado_em=timezone.now(),
        )
        if hasattr(candidature, "pedido_encerramento"):
            PedidoEncerramento.objects.filter(pk=candidature.pedido_encerramento.pk).update(
                estado=PedidoEncerramento.Estado.NAO_ACEITE,
                concluido_em=transition.efetiva_em,
                observacoes_decisao=motivo.strip(),
                atualizado_em=timezone.now(),
            )
    if code == "TR-014" and hasattr(candidature, "termo_aceitacao"):
        TermoAceitacao.objects.filter(pk=candidature.termo_aceitacao.pk).update(
            estado=TermoAceitacao.Estado.INVALIDO,
            justificacao=motivo.strip(),
            atualizado_em=timezone.now(),
        )
    if code in {"TR-005", "TR-012", "TR-014", "TR-022"}:
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
    closure_phase = candidature.estado_atual == Candidatura.Estado.ENCERRAMENTO_ANALISE
    code = "TR-018" if closure_phase else "TR-007"
    request_phase = (
        PedidoElementos.Fase.ENCERRAMENTO if closure_phase else PedidoElementos.Fase.ANALISE
    )
    suspended_type = Prazo.Tipo.REMANESCENTE if closure_phase else Prazo.Tipo.DECISAO
    existing = _obter_repetida(candidature, code, key)
    if existing:
        return existing, None
    definition = _validar_transicao(
        candidature=candidature,
        code=code,
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
        .filter(tipo=suspended_type, estado=Prazo.Estado.ATIVO)
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
        fase=request_phase,
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
        motivo=f"Pedido de elementos adicionais — {request.get_fase_display()}.",
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
    code = "TR-019" if request.fase == PedidoElementos.Fase.ENCERRAMENTO else "TR-008"
    existing = _obter_repetida(candidature, code, key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code=code,
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
def associar_termo_recebido(
    *,
    candidatura_id,
    documento,
    utilizador,
    versao_esperada,
    recebido_em,
    tipo_assinatura,
    justificacao="",
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato", "titular_empresa")
        .get(pk=candidatura_id)
    )
    if candidature.versao != versao_esperada:
        raise ConflitoWorkflow(
            "A candidatura foi alterada noutra sessão. Atualize a página e tente novamente."
        )
    if candidature.estado_atual != Candidatura.Estado.APROVADA_AGUARDA_TERMO:
        raise TransicaoInvalida("O termo só pode ser recebido enquanto a candidatura o aguarda.")
    if not utilizador_pode_operar_candidatura(utilizador, candidature):
        raise PermissionDenied("Não pode associar o termo desta candidatura.")
    term = TermoAceitacao.objects.select_for_update().get(candidatura=candidature)
    if documento.documento.candidatura_id != candidature.pk or not documento.corrente:
        raise ValidationError("Selecione a versão corrente de um documento desta candidatura.")
    if documento.documento.tipo_documento.codigo != "TERMO_ACEITACAO":
        raise ValidationError("O documento selecionado não é um termo de aceitação.")
    if tipo_assinatura not in TermoAceitacao.TipoAssinatura.values:
        raise ValidationError("Escolha um tipo de assinatura válido.")
    if not recebido_em:
        raise ValidationError("Indique quando o termo foi recebido.")
    if timezone.is_naive(recebido_em):
        recebido_em = timezone.make_aware(recebido_em)
    if term.notificado_em and recebido_em < term.notificado_em:
        raise ValidationError("A receção do termo não pode anteceder a notificação.")
    outside_deadline = bool(term.data_limite and recebido_em > term.data_limite)
    TermoAceitacao.objects.filter(pk=term.pk).update(
        estado=(
            TermoAceitacao.Estado.FORA_PRAZO if outside_deadline else TermoAceitacao.Estado.RECEBIDO
        ),
        recebido_em=recebido_em,
        tipo_assinatura=tipo_assinatura,
        fora_prazo=outside_deadline,
        documento=documento,
        justificacao=justificacao.strip(),
        atualizado_em=timezone.now(),
    )
    term.refresh_from_db()
    if outside_deadline:
        for user_id in _destinatarios(candidature, utilizador):
            Notificacao.objects.get_or_create(
                destinatario_id=user_id,
                chave_deduplicacao=f"termo:{term.pk}:fora-prazo",
                defaults={
                    "candidatura": candidature,
                    "codigo": "TERMO_FORA_PRAZO",
                    "titulo": "Termo recebido fora do prazo calculado",
                    "mensagem": (
                        "O atraso foi assinalado para análise; "
                        "não foi tomada uma decisão automática."
                    ),
                    "prioridade": Notificacao.Prioridade.ATENCAO,
                    "estado": Notificacao.Estado.ENVIADA,
                    "enviada_em": timezone.now(),
                },
            )
    return term


@transaction.atomic
def confirmar_termo_aceite(
    *,
    candidatura_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-013", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-013",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    term = (
        TermoAceitacao.objects.select_for_update()
        .select_related("documento")
        .get(candidatura=candidature)
    )
    if term.estado not in {TermoAceitacao.Estado.RECEBIDO, TermoAceitacao.Estado.FORA_PRAZO}:
        raise ValidationError("Registe primeiro a receção do termo de aceitação.")
    if not term.documento_id or not term.tipo_assinatura or not term.recebido_em:
        raise ValidationError("O termo não tem os dados de receção completos.")
    if (
        not term.documento.corrente
        or term.documento.estado_validacao != VersaoDocumento.EstadoValidacao.VALIDO
    ):
        raise ValidationError("A versão corrente do termo tem de estar validada.")
    normalized_effective = (
        timezone.make_aware(efetiva_em) if timezone.is_naive(efetiva_em) else efetiva_em
    )
    if normalized_effective < term.recebido_em:
        raise ValidationError("A confirmação do termo não pode anteceder a sua receção.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=normalized_effective,
        origin=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
        key=key,
        evidence=term.documento,
    )
    TermoAceitacao.objects.filter(pk=term.pk).update(
        estado=TermoAceitacao.Estado.VALIDADO,
        validado_em=transition.efetiva_em,
        validado_por=utilizador,
        atualizado_em=timezone.now(),
    )
    _concluir_prazos(candidature, {Prazo.Tipo.TERMO})
    _concluir_tarefas(candidature.tarefas.filter(termo_origem=term), utilizador)
    first_payment_deadline = _criar_prazo_dias_uteis(
        candidature,
        transition,
        type_code=Prazo.Tipo.PRIMEIRA_PRESTACAO,
        rule_code=CODIGO_PRAZO_PRIMEIRA_PRESTACAO,
    )
    task = _criar_tarefa(
        candidature,
        key=f"candidatura:{candidature.pk}:primeira-prestacao",
        type_code="ACOMPANHAR_PRIMEIRA_PRESTACAO",
        title="Acompanhar a primeira prestação",
        assigned_to=utilizador,
        deadline=first_payment_deadline.limite_efetivo,
        deadline_origin=first_payment_deadline,
    )
    _notificar_tarefa(task)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def registar_resultado_participacao(
    *,
    participacao_id,
    utilizador,
    estado,
    inicio_real=None,
    fim_real=None,
    horas_frequentadas=None,
    dias_tres_ou_mais_horas=None,
    custo_pago_formadora=None,
    motivo="",
):
    participation = (
        ParticipacaoFormacao.objects.select_for_update()
        .select_related(
            "beneficiario__candidatura__titular_candidato",
            "beneficiario__candidatura__titular_empresa",
            "acao_formacao",
        )
        .get(pk=participacao_id)
    )
    candidature = participation.beneficiario.candidatura
    if candidature.estado_atual != Candidatura.Estado.APROVADA_ACOMPANHAMENTO:
        raise TransicaoInvalida("A participação só pode ser atualizada durante o acompanhamento.")
    if not utilizador_pode_operar_candidatura(utilizador, candidature):
        raise PermissionDenied("Não pode atualizar esta participação.")
    terminal_states = {
        AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
        AcaoFormacao.Estado.CONCLUIDA_SEM_APROVEITAMENTO,
        AcaoFormacao.Estado.INTERROMPIDA,
        AcaoFormacao.Estado.CANCELADA,
    }
    allowed = {
        AcaoFormacao.Estado.PLANEADA: {AcaoFormacao.Estado.EM_CURSO, *terminal_states},
        AcaoFormacao.Estado.EM_CURSO: terminal_states,
    }
    if estado not in allowed.get(participation.estado, set()):
        raise ValidationError("A alteração de estado da participação não é permitida.")
    reason = motivo.strip()
    if estado in {AcaoFormacao.Estado.INTERROMPIDA, AcaoFormacao.Estado.CANCELADA} and not reason:
        raise ValidationError("A interrupção ou o cancelamento exige um motivo.")
    action = participation.acao_formacao
    action.inicio_real = inicio_real or action.inicio_real
    action.fim_real = fim_real or action.fim_real
    completed_states = {
        AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
        AcaoFormacao.Estado.CONCLUIDA_SEM_APROVEITAMENTO,
    }
    if estado in completed_states and (
        not action.inicio_real
        or not action.fim_real
        or horas_frequentadas is None
        or custo_pago_formadora is None
    ):
        raise ValidationError(
            "Uma formação concluída exige datas reais, horas frequentadas e custo pago."
        )
    if estado == AcaoFormacao.Estado.INTERROMPIDA and not action.inicio_real:
        raise ValidationError("Uma formação interrompida exige a data real de início.")
    action.estado = estado
    action.full_clean()
    action.save(update_fields=("inicio_real", "fim_real", "estado", "atualizado_em"))
    participation.estado = estado
    participation.horas_frequentadas = horas_frequentadas
    participation.dias_tres_ou_mais_horas = dias_tres_ou_mais_horas
    participation.custo_pago_formadora = custo_pago_formadora
    participation.motivo_resultado = reason
    participation.resultado_registado_em = timezone.now() if estado in terminal_states else None
    participation.full_clean()
    participation.save(
        update_fields=(
            "estado",
            "horas_frequentadas",
            "dias_tres_ou_mais_horas",
            "custo_pago_formadora",
            "motivo_resultado",
            "resultado_registado_em",
            "atualizado_em",
        )
    )
    if estado in {AcaoFormacao.Estado.INTERROMPIDA, AcaoFormacao.Estado.CANCELADA}:
        task = _criar_tarefa(
            candidature,
            key=f"participacao:{participation.pk}:analisar-consequencias",
            type_code="ANALISAR_OCORRENCIA_FORMACAO",
            title="Analisar consequências da ocorrência na formação",
            assigned_to=utilizador,
            beneficiary=participation.beneficiario,
            priority=Tarefa.Prioridade.ALTA,
        )
        _notificar_tarefa(task)
    return participation


def _participacoes_deferidas(candidature):
    return ParticipacaoFormacao.objects.filter(
        beneficiario__candidatura=candidature,
        beneficiario__resultado=BeneficiarioCandidatura.Resultado.DEFERIDA,
    ).select_related("beneficiario__candidato__utilizador", "acao_formacao")


def _validar_resultados_formacao(candidature):
    terminal_states = {
        AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
        AcaoFormacao.Estado.CONCLUIDA_SEM_APROVEITAMENTO,
        AcaoFormacao.Estado.INTERROMPIDA,
        AcaoFormacao.Estado.CANCELADA,
    }
    participations = list(_participacoes_deferidas(candidature))
    if not participations:
        raise ValidationError("Não existem participações deferidas para encerrar.")
    for participation in participations:
        if participation.estado not in terminal_states or not participation.resultado_registado_em:
            raise ValidationError(
                "Todas as participações deferidas precisam de um resultado final."
            )
        if not participation.acao_formacao.fim_real:
            raise ValidationError("Indique a data real de fim de todas as formações.")
        if (
            participation.estado
            in {AcaoFormacao.Estado.INTERROMPIDA, AcaoFormacao.Estado.CANCELADA}
            and not participation.motivo_resultado.strip()
        ):
            raise ValidationError("Justifique as participações interrompidas ou canceladas.")
    return participations


def _gerar_checklist_encerramento(candidature, participations, deadline, user):
    required_codes = {"DECLARACAO_FORMADORA", "COMPROVATIVO_PAGAMENTO"}
    if any(
        participation.estado
        in {
            AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
            AcaoFormacao.Estado.CONCLUIDA_SEM_APROVEITAMENTO,
        }
        for participation in participations
    ):
        required_codes.add("CERTIFICADO_FORMACAO")
    types = TipoDocumento.objects.filter(codigo__in=required_codes, ativo=True).in_bulk(
        field_name="codigo"
    )
    missing = required_codes - set(types)
    if missing:
        raise ValidationError(
            "Faltam tipos documentais ativos para o encerramento: " + ", ".join(sorted(missing))
        )
    created = []
    for participation in participations:
        codes = {"DECLARACAO_FORMADORA", "COMPROVATIVO_PAGAMENTO"}
        if participation.estado in {
            AcaoFormacao.Estado.CONCLUIDA_COM_APROVEITAMENTO,
            AcaoFormacao.Estado.CONCLUIDA_SEM_APROVEITAMENTO,
        }:
            codes.add("CERTIFICADO_FORMACAO")
        for code in sorted(codes):
            requirement, was_created = RequisitoDocumento.objects.get_or_create(
                candidatura=candidature,
                beneficiario=participation.beneficiario,
                participacao=participation,
                tipo_documento=types[code],
                fase=FaseDocumento.ENCERRAMENTO,
                defaults={
                    "codigo_regra": "RN-ENC-002"
                    if code == "CERTIFICADO_FORMACAO"
                    else "RN-ENC-003",
                    "data_limite": deadline,
                },
            )
            if was_created:
                created.append(requirement)
                task = _criar_tarefa(
                    candidature,
                    key=f"requisito:{requirement.pk}:encerramento",
                    type_code="DOCUMENTO_ENCERRAMENTO",
                    title=f"Entregar {requirement.tipo_documento.designacao}",
                    assigned_to=user,
                    beneficiary=participation.beneficiario,
                    deadline=deadline,
                    requirement=requirement,
                )
                _notificar_tarefa(task)
    return created


@transaction.atomic
def iniciar_preparacao_encerramento(
    *,
    candidatura_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-015", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-015",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    participations = _validar_resultados_formacao(candidature)
    normalized_effective = (
        timezone.make_aware(efetiva_em) if timezone.is_naive(efetiva_em) else efetiva_em
    )
    latest_end = max(participation.acao_formacao.fim_real for participation in participations)
    if timezone.localtime(normalized_effective).date() < latest_end:
        raise ValidationError("O encerramento não pode começar antes do fim real da formação.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=normalized_effective,
        origin=TransicaoCandidatura.Origem.UTILIZADOR,
        key=key,
    )
    deadline_start = timezone.make_aware(datetime.combine(latest_end, time.min))
    duration = _valor_inteiro(candidature, CODIGO_PRAZO_ENCERRAMENTO)
    deadline_limit = _limite_meses(deadline_start, duration)
    PedidoEncerramento.objects.create(
        candidatura=candidature,
        estado=PedidoEncerramento.Estado.PREPARACAO,
        preparacao_iniciada_em=transition.efetiva_em,
    )
    deadline = Prazo(
        candidatura=candidature,
        tipo=Prazo.Tipo.ENCERRAMENTO,
        codigo_regra=CODIGO_PRAZO_ENCERRAMENTO,
        conjunto_regras=candidature.conjunto_regras,
        inicio_em=deadline_start,
        unidade=Prazo.Unidade.MESES,
        duracao=duration,
        limite_calculado=deadline_limit,
        transicao_origem=transition,
    )
    deadline.full_clean()
    deadline.save()
    _gerar_checklist_encerramento(candidature, participations, deadline.limite_efetivo, utilizador)
    _concluir_prazos(candidature, {Prazo.Tipo.PRIMEIRA_PRESTACAO})
    _concluir_tarefas(candidature.tarefas.filter(tipo="ACOMPANHAR_PRIMEIRA_PRESTACAO"), utilizador)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def submeter_encerramento(
    *,
    candidatura_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    referencia_externa,
    evidencia=None,
    motivo_atraso="",
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-016", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-016",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    if not referencia_externa.strip():
        raise ValidationError("Indique a referência externa do pedido de encerramento.")
    blocking = candidature.requisitos_documentais.filter(
        fase=FaseDocumento.ENCERRAMENTO,
        obrigatorio=True,
        bloqueante=True,
    ).exclude(estado__in=(EstadoDocumento.VALIDO, EstadoDocumento.DISPENSADO))
    if blocking.exists():
        raise ValidationError("Existem documentos finais bloqueantes por resolver.")
    deadline = candidature.prazos.select_for_update().get(
        tipo=Prazo.Tipo.ENCERRAMENTO,
        estado=Prazo.Estado.ATIVO,
    )
    effective = timezone.make_aware(efetiva_em) if timezone.is_naive(efetiva_em) else efetiva_em
    if effective > deadline.limite_efetivo and not motivo_atraso.strip():
        raise ValidationError("A submissão fora de prazo exige uma justificação.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=effective,
        origin=TransicaoCandidatura.Origem.IEFPONLINE,
        key=key,
        external_reference=referencia_externa,
        reason=motivo_atraso,
        evidence=evidencia,
    )
    snapshot = criar_snapshot(
        candidatura_id=candidature.pk,
        utilizador=utilizador,
        finalidade=SnapshotSubmissao.Finalidade.ENCERRAMENTO,
        transicao=transition,
        dados_adicionais={"referencia_externa": referencia_externa.strip()},
    )
    closure = candidature.pedido_encerramento
    PedidoEncerramento.objects.filter(pk=closure.pk).update(
        estado=PedidoEncerramento.Estado.SUBMETIDO,
        submetido_em=transition.efetiva_em,
        referencia_externa=referencia_externa.strip(),
        snapshot_submissao=snapshot,
        atualizado_em=timezone.now(),
    )
    _concluir_prazos(candidature, {Prazo.Tipo.ENCERRAMENTO})
    _concluir_tarefas(
        candidature.tarefas.filter(requisito_origem__fase=FaseDocumento.ENCERRAMENTO),
        utilizador,
    )
    remaining_deadline = _criar_prazo_dias_uteis(
        candidature,
        transition,
        type_code=Prazo.Tipo.REMANESCENTE,
        rule_code=CODIGO_PRAZO_REMANESCENTE,
    )
    task = _criar_tarefa(
        candidature,
        key=f"candidatura:{candidature.pk}:acompanhar-encerramento",
        type_code="ACOMPANHAR_ENCERRAMENTO",
        title="Acompanhar a análise do encerramento",
        assigned_to=utilizador,
        deadline=remaining_deadline.limite_efetivo,
        closure=closure,
    )
    _notificar_tarefa(task)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def registar_conclusao_encerramento(
    *,
    candidatura_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    resultado_final,
    referencia_externa="",
    observacoes="",
    evidencia=None,
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-020", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-020",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    allowed_results = {
        PedidoEncerramento.ResultadoFinal.CONCLUIDO,
        PedidoEncerramento.ResultadoFinal.CONCLUIDO_PARCIAL,
    }
    if resultado_final not in allowed_results:
        raise ValidationError("A conclusão tem de indicar um resultado aceite, total ou parcial.")
    if not (referencia_externa.strip() or evidencia):
        raise ValidationError("Associe a referência ou evidência da conclusão oficial.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=efetiva_em,
        origin=TransicaoCandidatura.Origem.COMUNICACAO_IEFP,
        key=key,
        external_reference=referencia_externa,
        reason=observacoes,
        evidence=evidencia,
    )
    closure = candidature.pedido_encerramento
    PedidoEncerramento.objects.filter(pk=closure.pk).update(
        estado=PedidoEncerramento.Estado.CONCLUIDO,
        concluido_em=transition.efetiva_em,
        resultado_final=resultado_final,
        observacoes_decisao=observacoes.strip(),
        referencia_externa=referencia_externa.strip() or closure.referencia_externa,
        atualizado_em=timezone.now(),
    )
    _concluir_prazos(candidature, {Prazo.Tipo.REMANESCENTE})
    _concluir_tarefas(candidature.tarefas.filter(tipo="ACOMPANHAR_ENCERRAMENTO"), utilizador)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def confirmar_regularizacao_financeira(
    *,
    candidatura_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    regularizacao_confirmada,
    referencia_externa="",
    evidencia=None,
    sem_pagamento=False,
    motivo="",
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-021", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-021",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason="",
    )
    if not regularizacao_confirmada:
        raise ValidationError("Confirme que não existem movimentos financeiros pendentes.")
    if sem_pagamento and not motivo.strip():
        raise ValidationError("A decisão sem pagamento exige uma justificação.")
    if not sem_pagamento and not (referencia_externa.strip() or evidencia):
        raise ValidationError("Associe a referência ou evidência da regularização financeira.")
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
    BeneficiarioCandidatura.objects.filter(
        candidatura=candidature,
        resultado=BeneficiarioCandidatura.Resultado.DEFERIDA,
    ).update(
        resultado=BeneficiarioCandidatura.Resultado.ENCERRADA,
        decidido_em=transition.efetiva_em,
        motivo_decisao=motivo.strip() or "Encerramento e regularização financeira confirmados.",
        referencia_decisao=referencia_externa.strip(),
        atualizado_em=timezone.now(),
    )
    _cancelar_operacional(candidature, utilizador, transition.efetiva_em)
    _atualizar_candidatura(candidature, transition)
    _notificar_estado(candidature, transition)
    return transition


@transaction.atomic
def corrigir_estado_terminal(
    *,
    candidatura_id,
    utilizador,
    versao_esperada,
    chave_idempotencia,
    efetiva_em,
    motivo,
    confirmacao=False,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("titular_candidato__utilizador", "titular_empresa", "conjunto_regras")
        .get(pk=candidatura_id)
    )
    key = _normalizar_chave(chave_idempotencia)
    existing = _obter_repetida(candidature, "TR-023", key)
    if existing:
        return existing
    definition = _validar_transicao(
        candidature=candidature,
        code="TR-023",
        user=utilizador,
        expected_version=versao_esperada,
        confirmation=confirmacao,
        reason=motivo,
    )
    incorrect = candidature.transicoes.order_by("-registada_em", "-pk").first()
    if not incorrect or incorrect.estado_novo != candidature.estado_atual:
        raise ValidationError("Não foi possível identificar a última transição terminal.")
    if incorrect.codigo == "TR-023" or not incorrect.estado_anterior:
        raise ValidationError("A correção deve referir uma transição original válida.")
    transition = _criar_transicao(
        candidature=candidature,
        definition=definition,
        user=utilizador,
        effective_at=efetiva_em,
        origin=TransicaoCandidatura.Origem.UTILIZADOR,
        key=key,
        reason=motivo,
        new_state=incorrect.estado_anterior,
        corrects=incorrect,
    )
    if incorrect.codigo == "TR-022":
        BeneficiarioCandidatura.objects.filter(
            candidatura=candidature,
            resultado=BeneficiarioCandidatura.Resultado.REVOGADA,
        ).update(
            resultado=BeneficiarioCandidatura.Resultado.DEFERIDA,
            decidido_em=transition.efetiva_em,
            motivo_decisao="",
            atualizado_em=timezone.now(),
        )
        closure_states = {
            Candidatura.Estado.ENCERRAMENTO_PREPARACAO: PedidoEncerramento.Estado.PREPARACAO,
            Candidatura.Estado.ENCERRAMENTO_SUBMETIDO: PedidoEncerramento.Estado.SUBMETIDO,
            Candidatura.Estado.ENCERRAMENTO_ANALISE: PedidoEncerramento.Estado.EM_ANALISE,
            Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS: (
                PedidoEncerramento.Estado.AGUARDA_ELEMENTOS
            ),
            Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO: (PedidoEncerramento.Estado.CONCLUIDO),
        }
        if incorrect.estado_anterior in closure_states:
            PedidoEncerramento.objects.filter(candidatura=candidature).update(
                estado=closure_states[incorrect.estado_anterior],
                atualizado_em=timezone.now(),
            )
    if incorrect.codigo in {"TR-010", "TR-011"}:
        BeneficiarioCandidatura.objects.filter(candidatura=candidature).update(
            resultado=BeneficiarioCandidatura.Resultado.PENDENTE,
            decidido_em=None,
            motivo_decisao="",
            referencia_decisao="",
            atualizado_em=timezone.now(),
        )
    if incorrect.codigo == "TR-014":
        term = TermoAceitacao.objects.filter(candidatura=candidature).first()
        if term:
            restored_term_state = TermoAceitacao.Estado.PENDENTE
            if term.recebido_em:
                restored_term_state = (
                    TermoAceitacao.Estado.FORA_PRAZO
                    if term.fora_prazo
                    else TermoAceitacao.Estado.RECEBIDO
                )
            TermoAceitacao.objects.filter(pk=term.pk).update(
                estado=restored_term_state,
                justificacao="",
                atualizado_em=timezone.now(),
            )
    if incorrect.codigo == "TR-021":
        BeneficiarioCandidatura.objects.filter(
            candidatura=candidature,
            resultado=BeneficiarioCandidatura.Resultado.ENCERRADA,
        ).update(
            resultado=BeneficiarioCandidatura.Resultado.DEFERIDA,
            decidido_em=transition.efetiva_em,
            motivo_decisao="",
            referencia_decisao="",
            atualizado_em=timezone.now(),
        )
    task = _criar_tarefa(
        candidature,
        key=f"transicao:{transition.pk}:rever-efeitos",
        type_code="REVER_CORRECAO",
        title="Rever efeitos da correção administrativa",
        assigned_to=utilizador,
        priority=Tarefa.Prioridade.ALTA,
    )
    _notificar_tarefa(task)
    corrected_result = (
        Candidatura.ResultadoDecisao.PENDENTE if incorrect.codigo in {"TR-010", "TR-011"} else None
    )
    _atualizar_candidatura(candidature, transition, decision_result=corrected_result)
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
