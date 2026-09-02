from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_safe

from .models import ConjuntoRegras
from .services import publicar_conjunto, utilizador_pode_publicar_regras


@login_required
@require_safe
def lista_conjuntos(request):
    conjuntos = ConjuntoRegras.objects.prefetch_related("parametros")
    if not utilizador_pode_publicar_regras(request.user):
        conjuntos = conjuntos.exclude(estado=ConjuntoRegras.Estado.RASCUNHO)
    return render(
        request,
        "regras/lista_conjuntos.html",
        {
            "conjuntos": conjuntos,
            "pode_publicar": utilizador_pode_publicar_regras(request.user),
        },
    )


@login_required
@require_POST
def publicar(request, conjunto_id):
    try:
        conjunto = publicar_conjunto(conjunto_id, request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, f"O conjunto {conjunto} foi publicado.")
    return redirect("regras:lista_conjuntos")
