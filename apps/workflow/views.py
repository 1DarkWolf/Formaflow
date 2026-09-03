from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.candidaturas.models import Candidatura, ParticipacaoFormacao
from apps.candidaturas.selectors import (
    candidaturas_visiveis_por,
    utilizador_pode_consultar_equipa,
    utilizador_pode_operar_candidatura,
)
from apps.documentos.services import carregar_documento_workflow
from apps.organizacoes.selectors import utilizador_e_administrador

from .exceptions import ConflitoWorkflow, TransicaoInvalida
from .forms import (
    FormularioAcontecimento,
    FormularioConclusaoEncerramento,
    FormularioConfirmacaoWorkflow,
    FormularioCorrecao,
    FormularioDecisao,
    FormularioDocumentoWorkflow,
    FormularioParticipacao,
    FormularioPedidoElementos,
    FormularioRegularizacaoFinanceira,
    FormularioResposta,
    FormularioRespostaCompleta,
    FormularioSubmissaoEncerramento,
    FormularioTermoRecebido,
)
from .models import (
    Notificacao,
    PedidoElementos,
    QuestaoPedido,
    TermoAceitacao,
    TransicaoCandidatura,
)
from .notifications import marcar_notificacao_lida, resolver_notificacao
from .selectors import (
    pedidos_visiveis_por,
    proxima_acao,
    tarefas_visiveis_por,
    transicoes_visiveis_por,
    utilizador_pode_responder_questao,
)
from .services import (
    aplicar_transicao,
    associar_termo_recebido,
    confirmar_regularizacao_financeira,
    confirmar_termo_aceite,
    corrigir_estado_terminal,
    guardar_resposta_rascunho,
    iniciar_preparacao_encerramento,
    registar_conclusao_encerramento,
    registar_decisao,
    registar_pedido_elementos,
    registar_resposta_completa,
    registar_resultado_participacao,
    submeter_encerramento,
)
from .transitions import obter_transicao

CODIGOS_GERAIS = {
    "TR-002",
    "TR-003",
    "TR-004",
    "TR-005",
    "TR-006",
    "TR-012",
    "TR-014",
    "TR-017",
    "TR-022",
}


@login_required
@require_safe
def notificacoes(request):
    queryset = request.user.notificacoes.select_related("candidatura", "tarefa", "prazo")
    estado = str(request.GET.get("estado", "")).strip().upper()
    prioridade = str(request.GET.get("prioridade", "")).strip().upper()
    if estado in {value for value, _label in Notificacao.Estado.choices}:
        queryset = queryset.filter(estado=estado)
    else:
        estado = ""
    if prioridade in {value for value, _label in Notificacao.Prioridade.choices}:
        queryset = queryset.filter(prioridade=prioridade)
    else:
        prioridade = ""
    page = Paginator(queryset, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "workflow/notificacoes.html",
        {
            "notificacoes": page,
            "filtros": {"estado": estado, "prioridade": prioridade},
            "estados": Notificacao.Estado.choices,
            "prioridades": Notificacao.Prioridade.choices,
        },
    )


@login_required
@require_POST
def ler_notificacao(request, notificacao_id):
    marcar_notificacao_lida(notificacao_id=notificacao_id, utilizador=request.user)
    messages.success(request, "O aviso foi marcado como lido.")
    return redirect("workflow:notificacoes")


@login_required
@require_POST
def resolver_aviso(request, notificacao_id):
    resolver_notificacao(notificacao_id=notificacao_id, utilizador=request.user)
    messages.success(request, "O aviso foi resolvido.")
    return redirect("workflow:notificacoes")


def _obter_candidatura(user, public_id):
    return get_object_or_404(
        candidaturas_visiveis_por(user).select_related(
            "titular_candidato__utilizador",
            "titular_empresa",
            "conjunto_regras",
        ),
        public_id=public_id,
    )


def _pode_registar_oficial(user, candidature):
    return bool(
        utilizador_pode_operar_candidatura(user, candidature)
        and (
            utilizador_e_administrador(user) or utilizador_pode_consultar_equipa(user, candidature)
        )
    )


def _acoes_disponiveis(user, candidature):
    can_operate = utilizador_pode_operar_candidatura(user, candidature)
    can_official = _pode_registar_oficial(user, candidature)
    actions = []
    state = candidature.estado_atual
    if can_operate and state == Candidatura.Estado.RASCUNHO:
        actions.extend((obter_transicao("TR-002"), obter_transicao("TR-005")))
    elif can_operate and state == Candidatura.Estado.PRONTA_SUBMISSAO:
        actions.extend(
            (
                obter_transicao("TR-004"),
                obter_transicao("TR-003"),
                obter_transicao("TR-005"),
            )
        )
    elif can_official and state == Candidatura.Estado.SUBMETIDA:
        actions.extend((obter_transicao("TR-006"), obter_transicao("TR-012")))
    elif can_official and state == Candidatura.Estado.EM_ANALISE:
        actions.extend((obter_transicao("TR-007"), obter_transicao("TR-009")))
        actions.append(obter_transicao("TR-012"))
    elif can_official and state == Candidatura.Estado.AGUARDA_ELEMENTOS:
        actions.append(obter_transicao("TR-012"))
    elif state == Candidatura.Estado.APROVADA_AGUARDA_TERMO:
        if can_operate:
            actions.append(obter_transicao("TR-013"))
        if can_official:
            actions.extend((obter_transicao("TR-014"), obter_transicao("TR-022")))
    elif can_official and state == Candidatura.Estado.APROVADA_ACOMPANHAMENTO:
        actions.extend((obter_transicao("TR-015"), obter_transicao("TR-022")))
    elif can_official and state == Candidatura.Estado.ENCERRAMENTO_PREPARACAO:
        actions.extend((obter_transicao("TR-016"), obter_transicao("TR-022")))
    elif can_official and state == Candidatura.Estado.ENCERRAMENTO_SUBMETIDO:
        actions.extend((obter_transicao("TR-017"), obter_transicao("TR-022")))
    elif can_official and state == Candidatura.Estado.ENCERRAMENTO_ANALISE:
        actions.extend(
            (
                obter_transicao("TR-018"),
                obter_transicao("TR-020"),
                obter_transicao("TR-022"),
            )
        )
    elif can_official and state == Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS:
        actions.append(obter_transicao("TR-022"))
    elif can_official and state == Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO:
        actions.extend((obter_transicao("TR-021"), obter_transicao("TR-022")))
    elif utilizador_e_administrador(user) and state in obter_transicao("TR-023").origens:
        actions.append(obter_transicao("TR-023"))
    return actions


def _contexto_detalhe(user, candidature):
    return {
        "candidatura": candidature,
        "proxima_acao": proxima_acao(candidature),
        "acoes": _acoes_disponiveis(user, candidature),
        "transicoes": transicoes_visiveis_por(user, candidature).select_related(
            "ator", "evidencia"
        ),
        "pedidos": pedidos_visiveis_por(user, candidature),
        "prazos": candidature.prazos.prefetch_related("suspensoes"),
        "tarefas": tarefas_visiveis_por(user, candidature).select_related("atribuida_a"),
        "pode_operar": utilizador_pode_operar_candidatura(user, candidature),
        "participacoes": ParticipacaoFormacao.objects.filter(
            beneficiario__candidatura=candidature,
            beneficiario__resultado="DEFERIDA",
        ).select_related("beneficiario__candidato__utilizador", "acao_formacao"),
        "termo": getattr(candidature, "termo_aceitacao", None),
        "encerramento": getattr(candidature, "pedido_encerramento", None),
    }


@login_required
@require_safe
def detalhe(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    return render(request, "workflow/detalhe.html", _contexto_detalhe(request.user, candidature))


@login_required
@require_http_methods(["GET", "POST"])
def novo_documento(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if candidature.estado_atual not in {
        Candidatura.Estado.SUBMETIDA,
        Candidatura.Estado.EM_ANALISE,
        Candidatura.Estado.AGUARDA_ELEMENTOS,
        Candidatura.Estado.APROVADA_AGUARDA_TERMO,
        Candidatura.Estado.APROVADA_ACOMPANHAMENTO,
        Candidatura.Estado.ENCERRAMENTO_PREPARACAO,
        Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS,
        Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO,
    } or not utilizador_pode_operar_candidatura(request.user, candidature):
        raise PermissionDenied("Não pode guardar documentos nesta candidatura.")
    form = FormularioDocumentoWorkflow(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            carregar_documento_workflow(
                candidatura_id=candidature.pk,
                tipo_documento=form.cleaned_data["tipo_documento"],
                ficheiro=form.cleaned_data["ficheiro"],
                utilizador=request.user,
                titulo=form.cleaned_data["titulo"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "O documento de acompanhamento foi guardado.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/documento_novo.html",
        {"candidatura": candidature, "form": form},
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def novo_documento_questao(request, questao_id):
    question = get_object_or_404(
        QuestaoPedido.objects.select_related(
            "pedido__candidatura",
            "beneficiario__candidato",
            "tipo_documento_pedido",
        ),
        pk=questao_id,
    )
    additional_request = _obter_pedido(request.user, question.pedido_id)
    if not utilizador_pode_responder_questao(request.user, question):
        raise PermissionDenied("Não pode guardar documentos para esta questão.")
    form = FormularioDocumentoWorkflow(
        request.POST or None,
        request.FILES or None,
        tipo_documento=question.tipo_documento_pedido,
    )
    if request.method == "POST" and form.is_valid():
        try:
            carregar_documento_workflow(
                candidatura_id=additional_request.candidatura_id,
                tipo_documento=form.cleaned_data["tipo_documento"],
                ficheiro=form.cleaned_data["ficheiro"],
                utilizador=request.user,
                titulo=form.cleaned_data["titulo"],
                beneficiario=question.beneficiario,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "O documento da resposta foi guardado.")
            return redirect("workflow:detalhe_pedido", pedido_id=additional_request.pk)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/documento_novo.html",
        {
            "candidatura": additional_request.candidatura,
            "pedido": additional_request,
            "questao": question,
            "form": form,
        },
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def acontecimento(request, public_id, codigo):
    candidature = _obter_candidatura(request.user, public_id)
    code = codigo.strip().upper()
    definition = obter_transicao(code)
    if not definition or code not in CODIGOS_GERAIS:
        raise Http404("Acontecimento inexistente.")
    if code not in {item.codigo for item in _acoes_disponiveis(request.user, candidature)}:
        raise PermissionDenied("Este acontecimento não está disponível nesta fase.")
    form = FormularioAcontecimento(
        request.POST or None,
        candidatura=candidature,
        codigo=code,
    )
    if request.method == "POST" and form.is_valid():
        origin = TransicaoCandidatura.Origem.UTILIZADOR
        if code == "TR-004":
            origin = TransicaoCandidatura.Origem.IEFPONLINE
        elif code in {"TR-006", "TR-012", "TR-014", "TR-017", "TR-022"}:
            origin = TransicaoCandidatura.Origem.COMUNICACAO_IEFP
        try:
            aplicar_transicao(
                candidatura_id=candidature.pk,
                codigo=code,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                origem=origin,
                referencia_externa=form.cleaned_data.get("referencia_externa", ""),
                motivo=form.cleaned_data.get("motivo", ""),
                evidencia=form.cleaned_data.get("evidencia"),
                confirmacao=form.cleaned_data["confirmacao"],
                avisos_reconhecidos=form.cleaned_data.get("avisos_reconhecidos", False),
            )
        except ConflitoWorkflow as error:
            form.add_error(None, str(error))
            return render(
                request,
                "workflow/acontecimento.html",
                {"candidatura": candidature, "definicao": definition, "form": form},
                status=409,
            )
        except (ValidationError, TransicaoInvalida) as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"{definition.designacao} registado com sucesso.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/acontecimento.html",
        {"candidatura": candidature, "definicao": definition, "form": form},
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def novo_pedido(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if candidature.estado_atual not in {
        Candidatura.Estado.EM_ANALISE,
        Candidatura.Estado.ENCERRAMENTO_ANALISE,
    } or not _pode_registar_oficial(request.user, candidature):
        raise PermissionDenied("Não pode registar pedidos nesta candidatura.")
    form = FormularioPedidoElementos(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        questions = [
            {
                "texto": text,
                "destinatario": QuestaoPedido.Destinatario.EMPRESA
                if candidature.tipo == Candidatura.Tipo.EMPRESARIAL
                else QuestaoPedido.Destinatario.TITULAR,
            }
            for text in form.cleaned_data["questoes_normalizadas"]
        ]
        try:
            _, additional_request = registar_pedido_elementos(
                candidatura_id=candidature.pk,
                questoes=questions,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                recebido_em=form.cleaned_data["recebido_em"],
                referencia_externa=form.cleaned_data["referencia_externa"],
                descricao=form.cleaned_data["descricao"],
                evidencia=form.cleaned_data["evidencia"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except ConflitoWorkflow as error:
            form.add_error(None, str(error))
            return render(
                request,
                "workflow/pedido_novo.html",
                {"candidatura": candidature, "form": form},
                status=409,
            )
        except (ValidationError, TransicaoInvalida) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "O pedido de elementos foi registado.")
            if additional_request:
                return redirect("workflow:detalhe_pedido", pedido_id=additional_request.pk)
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/pedido_novo.html",
        {"candidatura": candidature, "form": form},
        status=status,
    )


def _obter_pedido(user, pedido_id):
    request_record = get_object_or_404(
        PedidoElementos.objects.select_related("candidatura"),
        pk=pedido_id,
    )
    return get_object_or_404(
        pedidos_visiveis_por(user, request_record.candidatura),
        pk=request_record.pk,
    )


def _contexto_pedido(user, additional_request, *, forms_by_question=None, complete_form=None):
    questions = list(
        additional_request.questoes.select_related(
            "beneficiario__candidato__utilizador",
            "tipo_documento_pedido",
        ).prefetch_related("respostas__versoes_documentos")
    )
    answer_forms = forms_by_question or {}
    for question in questions:
        answer_forms.setdefault(
            question.pk,
            FormularioResposta(questao=question, prefix=f"q{question.pk}"),
        )
        question.form_resposta = answer_forms[question.pk]
        question.pode_responder = utilizador_pode_responder_questao(user, question)
    return {
        "pedido": additional_request,
        "candidatura": additional_request.candidatura,
        "questoes": questions,
        "form_completo": complete_form
        or FormularioRespostaCompleta(candidatura=additional_request.candidatura),
        "pode_responder": utilizador_pode_operar_candidatura(user, additional_request.candidatura),
    }


@login_required
@require_safe
def detalhe_pedido(request, pedido_id):
    additional_request = _obter_pedido(request.user, pedido_id)
    return render(
        request,
        "workflow/detalhe_pedido.html",
        _contexto_pedido(request.user, additional_request),
    )


@login_required
@require_POST
def guardar_resposta(request, questao_id):
    question = get_object_or_404(
        QuestaoPedido.objects.select_related("pedido__candidatura"),
        pk=questao_id,
    )
    additional_request = _obter_pedido(request.user, question.pedido_id)
    form = FormularioResposta(request.POST, questao=question, prefix=f"q{question.pk}")
    if form.is_valid():
        try:
            guardar_resposta_rascunho(
                questao_id=question.pk,
                utilizador=request.user,
                texto=form.cleaned_data["texto"],
                versoes_documentos=form.cleaned_data["versoes_documentos"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A resposta foi guardada em rascunho.")
            return redirect("workflow:detalhe_pedido", pedido_id=additional_request.pk)
    return render(
        request,
        "workflow/detalhe_pedido.html",
        _contexto_pedido(
            request.user,
            additional_request,
            forms_by_question={question.pk: form},
        ),
        status=400,
    )


@login_required
@require_POST
def resposta_completa(request, pedido_id):
    additional_request = _obter_pedido(request.user, pedido_id)
    form = FormularioRespostaCompleta(
        request.POST,
        candidatura=additional_request.candidatura,
    )
    if form.is_valid():
        try:
            registar_resposta_completa(
                pedido_id=additional_request.pk,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except ConflitoWorkflow as error:
            form.add_error(None, str(error))
            status = 409
        except (ValidationError, TransicaoInvalida) as error:
            form.add_error(None, error)
            status = 400
        else:
            messages.success(request, "A resposta completa foi registada.")
            return redirect("workflow:detalhe", public_id=additional_request.candidatura.public_id)
    else:
        status = 400
    return render(
        request,
        "workflow/detalhe_pedido.html",
        _contexto_pedido(request.user, additional_request, complete_form=form),
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def decisao(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if candidature.estado_atual != Candidatura.Estado.EM_ANALISE or not _pode_registar_oficial(
        request.user, candidature
    ):
        raise PermissionDenied("Não pode registar a decisão nesta candidatura.")
    form = FormularioDecisao(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        try:
            registar_decisao(
                candidatura_id=candidature.pk,
                resultados=form.resultados(),
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                evidencia=form.cleaned_data["evidencia"],
                referencia_externa=form.cleaned_data["referencia_externa"],
                motivo=form.cleaned_data["motivo"],
                motivos_beneficiarios=form.motivos_beneficiarios(),
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except ConflitoWorkflow as error:
            form.add_error(None, str(error))
            return render(
                request,
                "workflow/decisao.html",
                {"candidatura": candidature, "form": form},
                status=409,
            )
        except (ValidationError, TransicaoInvalida) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A decisão oficial foi registada.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/decisao.html",
        {"candidatura": candidature, "form": form},
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def termo(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if (
        candidature.estado_atual != Candidatura.Estado.APROVADA_AGUARDA_TERMO
        or not utilizador_pode_operar_candidatura(request.user, candidature)
    ):
        raise PermissionDenied("O termo não está disponível nesta fase.")
    term_record = get_object_or_404(TermoAceitacao, candidatura=candidature)
    reception_form = FormularioTermoRecebido(
        request.POST if request.POST.get("acao") == "receber" else None,
        candidatura=candidature,
        prefix="rececao",
    )
    confirmation_form = FormularioConfirmacaoWorkflow(
        request.POST if request.POST.get("acao") == "confirmar" else None,
        candidatura=candidature,
        prefix="confirmacao",
    )
    if request.method == "POST" and request.POST.get("acao") == "receber":
        if reception_form.is_valid():
            try:
                associar_termo_recebido(
                    candidatura_id=candidature.pk,
                    documento=reception_form.cleaned_data["documento"],
                    utilizador=request.user,
                    versao_esperada=reception_form.cleaned_data["versao"],
                    recebido_em=reception_form.cleaned_data["recebido_em"],
                    tipo_assinatura=reception_form.cleaned_data["tipo_assinatura"],
                    justificacao=reception_form.cleaned_data["justificacao"],
                )
            except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
                reception_form.add_error(None, error)
            else:
                messages.success(request, "A receção do termo foi registada.")
                return redirect("workflow:termo", public_id=candidature.public_id)
    elif request.method == "POST" and request.POST.get("acao") == "confirmar":
        if not _pode_registar_oficial(request.user, candidature):
            raise PermissionDenied("A validação do termo exige um gestor autorizado.")
        if confirmation_form.is_valid():
            try:
                confirmar_termo_aceite(
                    candidatura_id=candidature.pk,
                    utilizador=request.user,
                    versao_esperada=confirmation_form.cleaned_data["versao"],
                    chave_idempotencia=confirmation_form.cleaned_data["chave_idempotencia"],
                    efetiva_em=confirmation_form.cleaned_data["efetiva_em"],
                    confirmacao=confirmation_form.cleaned_data["confirmacao"],
                )
            except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
                confirmation_form.add_error(None, error)
            else:
                messages.success(request, "O termo foi validado e o acompanhamento começou.")
                return redirect("workflow:detalhe", public_id=candidature.public_id)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/termo.html",
        {
            "candidatura": candidature,
            "termo": term_record,
            "form_rececao": reception_form,
            "form_confirmacao": confirmation_form,
            "pode_confirmar": _pode_registar_oficial(request.user, candidature),
        },
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def participacao(request, participacao_id):
    participation = get_object_or_404(
        ParticipacaoFormacao.objects.select_related(
            "beneficiario__candidatura", "beneficiario__candidato__utilizador", "acao_formacao"
        ),
        pk=participacao_id,
    )
    candidature = _obter_candidatura(request.user, participation.beneficiario.candidatura.public_id)
    if (
        candidature.estado_atual != Candidatura.Estado.APROVADA_ACOMPANHAMENTO
        or not utilizador_pode_operar_candidatura(request.user, candidature)
    ):
        raise PermissionDenied("A participação não pode ser atualizada nesta fase.")
    form = FormularioParticipacao(
        request.POST or None,
        participacao=participation,
    )
    if request.method == "POST" and form.is_valid():
        try:
            registar_resultado_participacao(
                participacao_id=participation.pk,
                utilizador=request.user,
                **form.cleaned_data,
            )
        except (ValidationError, TransicaoInvalida) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "O estado da participação foi atualizado.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    status = 400 if request.method == "POST" else 200
    return render(
        request,
        "workflow/formulario_fase.html",
        {
            "candidatura": candidature,
            "form": form,
            "titulo": "Atualizar participação na formação",
            "descricao": f"{participation.beneficiario.candidato} · {participation.acao_formacao}",
            "botao": "Guardar resultado",
        },
        status=status,
    )


def _render_formulario_fase(request, candidature, form, *, title, description, button, status=200):
    return render(
        request,
        "workflow/formulario_fase.html",
        {
            "candidatura": candidature,
            "form": form,
            "titulo": title,
            "descricao": description,
            "botao": button,
        },
        status=status,
    )


@login_required
@require_http_methods(["GET", "POST"])
def iniciar_encerramento(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if (
        candidature.estado_atual != Candidatura.Estado.APROVADA_ACOMPANHAMENTO
        or not _pode_registar_oficial(request.user, candidature)
    ):
        raise PermissionDenied("O encerramento não pode ser iniciado nesta fase.")
    form = FormularioConfirmacaoWorkflow(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        try:
            iniciar_preparacao_encerramento(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A preparação do encerramento foi iniciada.")
            return redirect("documentos:checklist", public_id=candidature.public_id)
    return _render_formulario_fase(
        request,
        candidature,
        form,
        title="Iniciar preparação do encerramento",
        description="Confirme que todas as participações deferidas têm resultado final.",
        button="Gerar checklist final",
        status=400 if request.method == "POST" else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def submissao_encerramento(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if (
        candidature.estado_atual != Candidatura.Estado.ENCERRAMENTO_PREPARACAO
        or not _pode_registar_oficial(request.user, candidature)
    ):
        raise PermissionDenied("O encerramento não pode ser submetido nesta fase.")
    form = FormularioSubmissaoEncerramento(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        try:
            submeter_encerramento(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                referencia_externa=form.cleaned_data["referencia_externa"],
                evidencia=form.cleaned_data["evidencia"],
                motivo_atraso=form.cleaned_data["motivo_atraso"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A submissão do encerramento foi registada.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    return _render_formulario_fase(
        request,
        candidature,
        form,
        title="Submeter pedido de encerramento",
        description="Só é possível continuar com todos os documentos finais resolvidos.",
        button="Registar submissão",
        status=400 if request.method == "POST" else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def conclusao_encerramento(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if (
        candidature.estado_atual != Candidatura.Estado.ENCERRAMENTO_ANALISE
        or not _pode_registar_oficial(request.user, candidature)
    ):
        raise PermissionDenied("A conclusão não pode ser registada nesta fase.")
    form = FormularioConclusaoEncerramento(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        try:
            registar_conclusao_encerramento(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                resultado_final=form.cleaned_data["resultado_final"],
                referencia_externa=form.cleaned_data["referencia_externa"],
                observacoes=form.cleaned_data["observacoes"],
                evidencia=form.cleaned_data["evidencia"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A conclusão oficial foi registada.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    return _render_formulario_fase(
        request,
        candidature,
        form,
        title="Registar conclusão do encerramento",
        description="Transcreva apenas o resultado que consta da comunicação oficial.",
        button="Registar conclusão",
        status=400 if request.method == "POST" else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def regularizacao_financeira(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if (
        candidature.estado_atual != Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO
        or not _pode_registar_oficial(request.user, candidature)
    ):
        raise PermissionDenied("A regularização não pode ser confirmada nesta fase.")
    form = FormularioRegularizacaoFinanceira(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        try:
            confirmar_regularizacao_financeira(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                regularizacao_confirmada=form.cleaned_data["regularizacao_confirmada"],
                referencia_externa=form.cleaned_data["referencia_externa"],
                evidencia=form.cleaned_data["evidencia"],
                sem_pagamento=form.cleaned_data["sem_pagamento"],
                motivo=form.cleaned_data["motivo"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A candidatura foi encerrada.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    return _render_formulario_fase(
        request,
        candidature,
        form,
        title="Confirmar regularização financeira",
        description=(
            "Este registo declarativo será conciliado com os movimentos financeiros "
            "no módulo seguinte."
        ),
        button="Encerrar candidatura",
        status=400 if request.method == "POST" else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def correcao_terminal(request, public_id):
    candidature = _obter_candidatura(request.user, public_id)
    if candidature.estado_atual not in obter_transicao(
        "TR-023"
    ).origens or not utilizador_e_administrador(request.user):
        raise PermissionDenied("A correção terminal exige um administrador.")
    form = FormularioCorrecao(request.POST or None, candidatura=candidature)
    if request.method == "POST" and form.is_valid():
        try:
            corrigir_estado_terminal(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
                efetiva_em=form.cleaned_data["efetiva_em"],
                motivo=form.cleaned_data["motivo"],
                confirmacao=form.cleaned_data["confirmacao"],
            )
        except (ValidationError, TransicaoInvalida, ConflitoWorkflow) as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A correção foi registada sem apagar o histórico.")
            return redirect("workflow:detalhe", public_id=candidature.public_id)
    return _render_formulario_fase(
        request,
        candidature,
        form,
        title="Corrigir último estado terminal",
        description="A operação anterior fica preservada e ligada a esta correção.",
        button="Registar correção",
        status=400 if request.method == "POST" else 200,
    )
