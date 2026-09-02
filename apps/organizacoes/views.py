from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from .selectors import empresas_visiveis_por, utilizador_pode_consultar_detalhes


@login_required
@require_safe
def lista_empresas(request):
    empresas = empresas_visiveis_por(request.user)
    return render(request, "organizacoes/lista_empresas.html", {"empresas": empresas})


@login_required
@require_safe
def detalhe_empresa(request, public_id):
    empresa = get_object_or_404(empresas_visiveis_por(request.user), public_id=public_id)
    contexto = {
        "empresa": empresa,
        "mostrar_dados_institucionais": utilizador_pode_consultar_detalhes(request.user, empresa),
    }
    return render(request, "organizacoes/detalhe_empresa.html", contexto)
