import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from .exceptions import ConflitoVersao
from .forms import (
    AdicionarBeneficiarioForm,
    AdicionarFormacaoForm,
    DefinirContaPagamentoForm,
    NovaCandidaturaForm,
)
from .models import Candidatura
from .selectors import (
    beneficiarios_visiveis_por,
    candidaturas_visiveis_por,
    filtrar_candidaturas,
    utilizador_pode_editar_candidatura,
)
from .services import (
    adicionar_beneficiario,
    criar_candidatura_empresarial,
    criar_candidatura_individual,
    criar_formacao_para_beneficiario,
    definir_conta_pagamento,
    executar_verificacoes_basicas,
)


def _obter_candidatura(user, public_id):
    return get_object_or_404(
        candidaturas_visiveis_por(user).select_related(
            "titular_candidato__utilizador",
            "titular_empresa",
            "conta_pagamento",
            "conjunto_regras",
        ),
        public_id=public_id,
    )


def _contexto_detalhe(candidatura, user, *, formulario_ativo=None):
    can_edit = utilizador_pode_editar_candidatura(user, candidatura)
    visible_beneficiaries = (
        beneficiarios_visiveis_por(user, candidatura)
        .select_related(
            "candidato__utilizador",
            "vinculo_referencia",
        )
        .prefetch_related(
            "participacoes_formacao__acao_formacao__componentes",
        )
    )
    visible_ids = visible_beneficiaries.values("pk")
    checks = candidatura.verificacoes_elegibilidade.filter(
        Q(beneficiario__isnull=True) | Q(beneficiario_id__in=visible_ids)
    ).select_related("beneficiario__candidato__utilizador", "participacao__acao_formacao")
    has_beneficiaries = visible_beneficiaries.exists()
    context = {
        "candidatura": candidatura,
        "beneficiarios": visible_beneficiaries,
        "verificacoes": checks,
        "pode_editar": can_edit,
        "passo_beneficiarios_concluido": has_beneficiaries,
        "passo_formacao_concluido": has_beneficiaries
        and all(
            beneficiary.participacoes_formacao.exists() for beneficiary in visible_beneficiaries
        ),
    }
    if can_edit:
        default_forms = {
            "form_beneficiario": AdicionarBeneficiarioForm(candidatura=candidatura),
            "form_formacao": AdicionarFormacaoForm(candidatura=candidatura),
            "form_conta": DefinirContaPagamentoForm(candidatura=candidatura),
        }
        if formulario_ativo:
            default_forms.update(formulario_ativo)
        context.update(default_forms)
    return context


def _render_detalhe(request, candidatura, *, formulario_ativo=None, status=200):
    candidatura.refresh_from_db()
    return render(
        request,
        "candidaturas/detalhe.html",
        _contexto_detalhe(candidatura, request.user, formulario_ativo=formulario_ativo),
        status=status,
    )


@login_required
@require_safe
def lista(request):
    applications = candidaturas_visiveis_por(request.user).select_related(
        "titular_candidato__utilizador",
        "titular_empresa",
        "conjunto_regras",
    )
    applications, filters = filtrar_candidaturas(applications, request.GET)
    page = Paginator(applications, 12).get_page(request.GET.get("page"))
    query_filters = urlencode({key: value for key, value in filters.items() if value})
    return render(
        request,
        "candidaturas/lista.html",
        {
            "candidaturas": page,
            "filtros": filters,
            "estados": Candidatura.Estado.choices,
            "tipos": Candidatura.Tipo.choices,
            "query_filtros": query_filters,
        },
    )


@login_required
@require_safe
def exportar_csv(request):
    from apps.auditoria.services import registar_evento
    from apps.workflow.selectors import proxima_acao

    applications = candidaturas_visiveis_por(request.user).select_related(
        "titular_candidato__utilizador",
        "titular_empresa",
    )
    applications, filters = filtrar_candidaturas(applications, request.GET)
    rows = list(applications)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="candidaturas-formaflow.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        [
            "Identificador",
            "Tipo",
            "Estado",
            "Resultado",
            "Submetida em",
            "Próxima ação",
        ]
    )
    for application in rows:
        writer.writerow(
            [
                application.public_id,
                application.get_tipo_display(),
                application.get_estado_atual_display(),
                application.get_resultado_decisao_display(),
                application.submetida_em.isoformat() if application.submetida_em else "",
                proxima_acao(application),
            ]
        )

    registar_evento(
        acao="EXPORTAR_CANDIDATURAS_CSV",
        tipo_objeto="Candidatura",
        utilizador=request.user,
        request=request,
        metadados={
            "formato": "CSV",
            "quantidade": len(rows),
            "filtros": {
                "estado": filters["estado"],
                "tipo": filters["tipo"],
                "pesquisa_aplicada": bool(filters["q"]),
            },
        },
    )
    return response


@login_required
def nova(request):
    form = NovaCandidaturaForm(request.POST or None, utilizador=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["tipo"] == Candidatura.Tipo.INDIVIDUAL:
                application = criar_candidatura_individual(
                    criada_por=request.user,
                    vinculo_referencia=form.cleaned_data["vinculo"],
                    conjunto_regras=form.cleaned_data["conjunto_regras"],
                )
            else:
                application = criar_candidatura_empresarial(
                    criada_por=request.user,
                    titular_empresa=form.cleaned_data["empresa"],
                    conjunto_regras=form.cleaned_data["conjunto_regras"],
                )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "O rascunho da candidatura foi criado.")
            return redirect("candidaturas:detalhe", public_id=application.public_id)
    return render(request, "candidaturas/nova.html", {"form": form})


@login_required
@require_safe
def detalhe(request, public_id):
    application = _obter_candidatura(request.user, public_id)
    return _render_detalhe(request, application)


@login_required
@require_POST
def adicionar_beneficiario_view(request, public_id):
    application = _obter_candidatura(request.user, public_id)
    form = AdicionarBeneficiarioForm(request.POST, candidatura=application)
    if form.is_valid():
        try:
            adicionar_beneficiario(
                candidatura_id=application.pk,
                candidato=form.cleaned_data["candidato"],
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
            )
        except ConflitoVersao as error:
            form.add_error(None, str(error))
            return _render_detalhe(
                request,
                application,
                formulario_ativo={"form_beneficiario": form},
                status=409,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "O beneficiário foi adicionado.")
            return redirect("candidaturas:detalhe", public_id=application.public_id)
    return _render_detalhe(
        request,
        application,
        formulario_ativo={"form_beneficiario": form},
        status=400,
    )


@login_required
@require_POST
def adicionar_formacao_view(request, public_id):
    application = _obter_candidatura(request.user, public_id)
    form = AdicionarFormacaoForm(request.POST, candidatura=application)
    if form.is_valid():
        try:
            criar_formacao_para_beneficiario(
                candidatura_id=application.pk,
                beneficiario=form.cleaned_data["beneficiario"],
                dados_acao=form.dados_acao(),
                dados_componente=form.dados_componente(),
                custo_declarado=form.cleaned_data["custo_declarado"],
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
            )
        except ConflitoVersao as error:
            form.add_error(None, str(error))
            return _render_detalhe(
                request,
                application,
                formulario_ativo={"form_formacao": form},
                status=409,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A formação foi associada ao beneficiário.")
            return redirect("candidaturas:detalhe", public_id=application.public_id)
    return _render_detalhe(
        request,
        application,
        formulario_ativo={"form_formacao": form},
        status=400,
    )


@login_required
@require_POST
def definir_conta_view(request, public_id):
    application = _obter_candidatura(request.user, public_id)
    form = DefinirContaPagamentoForm(request.POST, candidatura=application)
    if form.is_valid():
        try:
            definir_conta_pagamento(
                candidatura_id=application.pk,
                conta_pagamento=form.cleaned_data["conta_pagamento"],
                utilizador=request.user,
                versao_esperada=form.cleaned_data["versao"],
            )
        except ConflitoVersao as error:
            form.add_error(None, str(error))
            return _render_detalhe(
                request,
                application,
                formulario_ativo={"form_conta": form},
                status=409,
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "A conta de pagamento foi guardada.")
            return redirect("candidaturas:detalhe", public_id=application.public_id)
    return _render_detalhe(
        request,
        application,
        formulario_ativo={"form_conta": form},
        status=400,
    )


@login_required
@require_POST
def verificar(request, public_id):
    application = _obter_candidatura(request.user, public_id)
    executar_verificacoes_basicas(
        candidatura_id=application.pk,
        utilizador=request.user,
    )
    messages.success(request, "As verificações básicas foram atualizadas.")
    return redirect("candidaturas:detalhe", public_id=application.public_id)
