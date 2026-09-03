from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from apps.candidaturas.selectors import (
    candidaturas_visiveis_por,
    utilizador_pode_operar_candidatura,
)

from .forms import (
    FormularioCalculo,
    FormularioConfirmacaoOficial,
    FormularioMovimento,
    FormularioRegularizacaoRestituicao,
    FormularioRestituicao,
    FormularioRisco,
)
from .selectors import (
    apoios_visiveis_por,
    movimentos_visiveis_por,
    restituicoes_visiveis_por,
)
from .services import (
    atualizar_restituicao,
    calcular_estimativas_candidatura,
    confirmar_valores_oficiais,
    registar_movimento,
    registar_restituicao_oficial,
    registar_risco_restituicao,
    total_confirmado_apoio,
    utilizador_pode_gerir_financeiro,
)


def _candidatura(utilizador, public_id):
    return get_object_or_404(
        candidaturas_visiveis_por(utilizador).select_related(
            "conjunto_regras", "titular_candidato", "titular_empresa"
        ),
        public_id=public_id,
    )


def _redirect(candidatura):
    return redirect("financeiro:detalhe", public_id=candidatura.public_id)


def _adicionar_erro(request, error):
    if hasattr(error, "messages"):
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.error(request, str(error))


@login_required
@require_safe
def detalhe_financeiro(request, public_id):
    candidature = _candidatura(request.user, public_id)
    supports = apoios_visiveis_por(request.user, candidature)
    support_rows = [
        {"apoio": support, "total_confirmado": total_confirmado_apoio(support)}
        for support in supports
    ]
    can_manage = utilizador_pode_gerir_financeiro(request.user, candidature)
    refunds = restituicoes_visiveis_por(request.user, candidature)
    return render(
        request,
        "financeiro/detalhe.html",
        {
            "candidatura": candidature,
            "linhas_apoio": support_rows,
            "movimentos": movimentos_visiveis_por(request.user, candidature),
            "restituicoes": refunds,
            "pode_gerir": can_manage,
            "pode_calcular": utilizador_pode_operar_candidatura(request.user, candidature),
            "form_calculo": FormularioCalculo(candidatura=candidature),
            "form_confirmacao": FormularioConfirmacaoOficial(
                candidatura=candidature, apoios=supports
            ),
            "form_movimento": FormularioMovimento(candidatura=candidature, apoios=supports),
            "form_risco": FormularioRisco(candidatura=candidature),
            "form_restituicao": FormularioRestituicao(candidatura=candidature),
            "form_regularizacao_restituicao": FormularioRegularizacaoRestituicao(
                candidatura=candidature, restituicoes=refunds
            ),
        },
    )


@login_required
@require_POST
def calcular(request, public_id):
    candidature = _candidatura(request.user, public_id)
    form = FormularioCalculo(request.POST, candidatura=candidature)
    if form.is_valid():
        third_party, social = form.opcoes()
        try:
            calcular_estimativas_candidatura(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                usar_valores_finais=form.cleaned_data["usar_valores_finais"],
                financiamentos_terceiros=third_party,
                apoios_sociais=social,
            )
        except ValidationError as error:
            _adicionar_erro(request, error)
        else:
            messages.success(request, "As estimativas foram recalculadas.")
    else:
        messages.error(request, "Corrija os dados usados no cálculo.")
    return _redirect(candidature)


@login_required
@require_POST
def confirmar(request, public_id):
    candidature = _candidatura(request.user, public_id)
    supports = apoios_visiveis_por(request.user, candidature)
    form = FormularioConfirmacaoOficial(request.POST, candidatura=candidature, apoios=supports)
    if form.is_valid():
        data = form.cleaned_data
        try:
            confirmar_valores_oficiais(
                apoio_id=data["apoio"].pk,
                utilizador=request.user,
                valor_aprovado=data["valor_aprovado"],
                valor_final=data["valor_final"],
                confirmado_em=data["confirmado_em"],
                referencia_externa=data["referencia_externa"],
                evidencia=data["evidencia"],
            )
        except ValidationError as error:
            _adicionar_erro(request, error)
        else:
            messages.success(request, "Os valores oficiais foram registados.")
    else:
        messages.error(request, "Corrija a confirmação dos valores oficiais.")
    return _redirect(candidature)


@login_required
@require_POST
def movimento(request, public_id):
    candidature = _candidatura(request.user, public_id)
    supports = apoios_visiveis_por(request.user, candidature)
    form = FormularioMovimento(request.POST, candidatura=candidature, apoios=supports)
    if form.is_valid():
        data = form.cleaned_data
        try:
            registar_movimento(
                apoio_id=data["apoio"].pk,
                utilizador=request.user,
                tipo=data["tipo"],
                direcao=data["direcao"],
                valor=data["valor"],
                estado=data["estado"],
                chave_idempotencia=data["chave_idempotencia"],
                previsto_para=data["previsto_para"],
                efetivado_em=data["efetivado_em"],
                referencia_externa=data["referencia_externa"],
                comprovativo=data["comprovativo"],
            )
        except ValidationError as error:
            _adicionar_erro(request, error)
        else:
            messages.success(request, "O movimento financeiro foi registado.")
    else:
        messages.error(request, "Corrija os dados do movimento.")
    return _redirect(candidature)


@login_required
@require_POST
def risco(request, public_id):
    candidature = _candidatura(request.user, public_id)
    form = FormularioRisco(request.POST, candidatura=candidature)
    if form.is_valid():
        try:
            registar_risco_restituicao(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                motivo=form.cleaned_data["motivo"],
                chave_idempotencia=form.cleaned_data["chave_idempotencia"],
            )
        except ValidationError as error:
            _adicionar_erro(request, error)
        else:
            messages.warning(
                request,
                "O risco originou uma tarefa de análise; não foi criada uma dívida automática.",
            )
    else:
        messages.error(request, "Descreva o risco identificado.")
    return _redirect(candidature)


@login_required
@require_POST
def restituicao(request, public_id):
    candidature = _candidatura(request.user, public_id)
    form = FormularioRestituicao(request.POST, candidatura=candidature)
    if form.is_valid():
        data = form.cleaned_data
        try:
            registar_restituicao_oficial(
                candidatura_id=candidature.pk,
                utilizador=request.user,
                beneficiario=data["beneficiario"],
                notificada_em=data["notificada_em"],
                valor=data["valor"],
                motivo=data["motivo"],
                chave_idempotencia=data["chave_idempotencia"],
                referencia_externa=data["referencia_externa"],
                evidencia=data["evidencia"],
            )
        except ValidationError as error:
            _adicionar_erro(request, error)
        else:
            messages.success(request, "A restituição oficial e o prazo foram registados.")
    else:
        messages.error(request, "Corrija os dados da restituição.")
    return _redirect(candidature)


@login_required
@require_POST
def regularizar_restituicao(request, public_id):
    candidature = _candidatura(request.user, public_id)
    refunds = restituicoes_visiveis_por(request.user, candidature)
    form = FormularioRegularizacaoRestituicao(
        request.POST, candidatura=candidature, restituicoes=refunds
    )
    if form.is_valid():
        data = form.cleaned_data
        try:
            atualizar_restituicao(
                restituicao_id=data["restituicao"].pk,
                utilizador=request.user,
                valor_restituido=data["valor_restituido"],
                regularizada_em=data["regularizada_em"],
                dispensada=data["dispensada"],
                referencia_externa=data["referencia_externa"],
                evidencia=data["evidencia"],
            )
        except ValidationError as error:
            _adicionar_erro(request, error)
        else:
            messages.success(request, "A regularização da restituição foi atualizada.")
    else:
        messages.error(request, "Corrija os dados da regularização.")
    return _redirect(candidature)
