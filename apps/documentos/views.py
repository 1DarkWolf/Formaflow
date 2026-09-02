import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from apps.candidaturas.selectors import (
    candidaturas_visiveis_por,
    utilizador_pode_editar_candidatura,
)

from .forms import (
    DispensarRequisitoForm,
    SnapshotForm,
    SubstituirDocumentoForm,
    UploadDocumentoForm,
    ValidarDocumentoForm,
)
from .models import Documento, RequisitoDocumento, VersaoDocumento
from .selectors import documentos_visiveis_por, requisitos_visiveis_por
from .services import (
    abrir_ficheiro_privado,
    carregar_para_requisito,
    criar_snapshot,
    dispensar_requisito,
    gerar_checklist_preparacao,
    substituir_documento,
    utilizador_pode_carregar_requisito,
    utilizador_pode_substituir_documento,
    utilizador_pode_validar_documentos,
    validar_versao,
)

logger = logging.getLogger("formaflow.documentos")


def _candidatura_visivel(user, public_id):
    return get_object_or_404(
        candidaturas_visiveis_por(user).select_related(
            "titular_candidato__utilizador", "titular_empresa", "conjunto_regras"
        ),
        public_id=public_id,
    )


def _erro_formulario(request, form, candidature, heading):
    return render(
        request,
        "documentos/erro_formulario.html",
        {"form": form, "candidatura": candidature, "titulo_erro": heading},
        status=400,
    )


@login_required
@require_safe
def checklist_view(request, public_id):
    candidature = _candidatura_visivel(request.user, public_id)
    requirements = (
        requisitos_visiveis_por(request.user, candidature)
        .select_related(
            "tipo_documento",
            "beneficiario__candidato__utilizador",
            "participacao__acao_formacao",
            "dispensado_por",
        )
        .prefetch_related("documentos__versoes__ficheiro", "documentos__versoes__validada_por")
    )
    requirement_list = list(requirements)
    for requirement in requirement_list:
        requirement.pode_carregar = utilizador_pode_carregar_requisito(request.user, requirement)
    valid_count = sum(item.estado in {"VALIDO", "DISPENSADO"} for item in requirement_list)
    can_edit = utilizador_pode_editar_candidatura(request.user, candidature)
    can_validate = utilizador_pode_validar_documentos(request.user, candidature)
    return render(
        request,
        "documentos/checklist.html",
        {
            "candidatura": candidature,
            "requisitos": requirement_list,
            "validos": valid_count,
            "total": len(requirement_list),
            "pode_editar": can_edit,
            "pode_validar": can_validate,
            "upload_form": UploadDocumentoForm(),
            "replace_form": SubstituirDocumentoForm(),
            "validation_form": ValidarDocumentoForm(),
            "waiver_form": DispensarRequisitoForm(),
            "snapshot_form": SnapshotForm(),
        },
    )


@login_required
@require_POST
def gerar_checklist_view(request, public_id):
    candidature = _candidatura_visivel(request.user, public_id)
    try:
        created = gerar_checklist_preparacao(candidatura_id=candidature.pk, utilizador=request.user)
    except ValidationError as error:
        messages.error(request, "; ".join(error.messages))
    else:
        messages.success(
            request,
            f"Checklist atualizada: {len(created)} novo(s) requisito(s).",
        )
    return redirect("documentos:checklist", public_id=candidature.public_id)


@login_required
@require_POST
def carregar_view(request, requisito_id):
    requirement = get_object_or_404(
        RequisitoDocumento.objects.select_related("candidatura"), pk=requisito_id
    )
    candidature = _candidatura_visivel(request.user, requirement.candidatura.public_id)
    if not requisitos_visiveis_por(request.user, candidature).filter(pk=requirement.pk).exists():
        raise Http404
    form = UploadDocumentoForm(request.POST, request.FILES)
    if not form.is_valid():
        return _erro_formulario(request, form, candidature, "Não foi possível carregar o documento")
    try:
        carregar_para_requisito(
            requisito_id=requirement.pk,
            ficheiro=form.cleaned_data["ficheiro"],
            utilizador=request.user,
            titulo=form.cleaned_data["titulo"],
            emitido_em=form.cleaned_data["emitido_em"],
            valido_ate=form.cleaned_data["valido_ate"],
        )
    except ValidationError as error:
        form.add_error("ficheiro", error)
        return _erro_formulario(request, form, candidature, "Não foi possível carregar o documento")
    messages.success(request, "Documento recebido e guardado na área privada.")
    return redirect("documentos:checklist", public_id=candidature.public_id)


@login_required
@require_POST
def substituir_view(request, public_id):
    document = get_object_or_404(
        Documento.objects.select_related("candidatura"), public_id=public_id
    )
    candidature = _candidatura_visivel(request.user, document.candidatura.public_id)
    if not documentos_visiveis_por(request.user, candidature).filter(pk=document.pk).exists():
        raise Http404
    form = SubstituirDocumentoForm(request.POST, request.FILES)
    if not form.is_valid():
        return _erro_formulario(
            request, form, candidature, "Não foi possível substituir o documento"
        )
    try:
        substituir_documento(
            documento_id=document.pk,
            ficheiro=form.cleaned_data["ficheiro"],
            motivo=form.cleaned_data["motivo"],
            utilizador=request.user,
            emitido_em=form.cleaned_data["emitido_em"],
            valido_ate=form.cleaned_data["valido_ate"],
        )
    except ValidationError as error:
        form.add_error(None, error)
        return _erro_formulario(
            request, form, candidature, "Não foi possível substituir o documento"
        )
    messages.success(request, "Nova versão carregada sem apagar o histórico.")
    return redirect("documentos:historico", public_id=document.public_id)


@login_required
@require_safe
def historico_view(request, public_id):
    document = get_object_or_404(
        Documento.objects.select_related("candidatura"), public_id=public_id
    )
    candidature = _candidatura_visivel(request.user, document.candidatura.public_id)
    document = get_object_or_404(
        documentos_visiveis_por(request.user, candidature).select_related(
            "tipo_documento", "beneficiario__candidato__utilizador", "participacao__acao_formacao"
        ),
        pk=document.pk,
    )
    return render(
        request,
        "documentos/historico.html",
        {
            "candidatura": candidature,
            "documento": document,
            "versoes": document.versoes.select_related("ficheiro", "carregada_por", "validada_por"),
            "pode_substituir": utilizador_pode_substituir_documento(request.user, document),
            "replace_form": SubstituirDocumentoForm(),
        },
    )


@login_required
@require_safe
def descarregar_view(request, public_id, numero):
    document = get_object_or_404(
        Documento.objects.select_related("candidatura"), public_id=public_id
    )
    candidature = _candidatura_visivel(request.user, document.candidatura.public_id)
    document = get_object_or_404(documentos_visiveis_por(request.user, candidature), pk=document.pk)
    version = get_object_or_404(
        VersaoDocumento.objects.select_related("ficheiro"),
        documento=document,
        numero=numero,
    )
    try:
        handle = abrir_ficheiro_privado(version)
    except (ValidationError, OSError):
        raise Http404 from None
    logger.info(
        "document_download autorizado user_id=%s document_public_id=%s version=%s",
        request.user.pk,
        document.public_id,
        version.numero,
    )
    response = FileResponse(
        handle,
        as_attachment=True,
        filename=version.ficheiro.nome_original,
        content_type=version.ficheiro.tipo_mime,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def validar_view(request, versao_id):
    version = get_object_or_404(
        VersaoDocumento.objects.select_related("documento__candidatura"), pk=versao_id
    )
    candidature = _candidatura_visivel(request.user, version.documento.candidatura.public_id)
    if (
        not documentos_visiveis_por(request.user, candidature)
        .filter(pk=version.documento_id)
        .exists()
    ):
        raise Http404
    form = ValidarDocumentoForm(request.POST)
    if not form.is_valid():
        return _erro_formulario(request, form, candidature, "A validação não foi guardada")
    try:
        validar_versao(
            versao_id=version.pk,
            utilizador=request.user,
            resultado=form.cleaned_data["resultado"],
            observacao=form.cleaned_data["observacao"],
        )
    except ValidationError as error:
        form.add_error(None, error)
        return _erro_formulario(request, form, candidature, "A validação não foi guardada")
    messages.success(request, "Validação documental guardada.")
    return redirect("documentos:checklist", public_id=candidature.public_id)


@login_required
@require_POST
def dispensar_view(request, requisito_id):
    requirement = get_object_or_404(
        RequisitoDocumento.objects.select_related("candidatura"), pk=requisito_id
    )
    candidature = _candidatura_visivel(request.user, requirement.candidatura.public_id)
    if not requisitos_visiveis_por(request.user, candidature).filter(pk=requirement.pk).exists():
        raise Http404
    form = DispensarRequisitoForm(request.POST)
    if not form.is_valid():
        return _erro_formulario(request, form, candidature, "A dispensa não foi guardada")
    dispensar_requisito(
        requisito_id=requirement.pk,
        utilizador=request.user,
        motivo=form.cleaned_data["motivo"],
    )
    messages.success(request, "Requisito dispensado com justificação registada.")
    return redirect("documentos:checklist", public_id=candidature.public_id)


@login_required
@require_POST
def snapshot_view(request, public_id):
    candidature = _candidatura_visivel(request.user, public_id)
    form = SnapshotForm(request.POST)
    if not form.is_valid():
        return _erro_formulario(request, form, candidature, "A fotografia não foi criada")
    try:
        snapshot = criar_snapshot(
            candidatura_id=candidature.pk,
            utilizador=request.user,
            finalidade=form.cleaned_data["finalidade"],
        )
    except ValidationError as error:
        form.add_error(None, error)
        return _erro_formulario(request, form, candidature, "A fotografia não foi criada")
    messages.success(
        request,
        f"Fotografia imutável {snapshot.get_finalidade_display()} #{snapshot.sequencia} criada.",
    )
    return redirect("documentos:checklist", public_id=candidature.public_id)
