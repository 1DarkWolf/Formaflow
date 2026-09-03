"""URL configuration for Forma Flow."""

from django.contrib import admin
from django.urls import include, path

handler400 = "apps.core.views.erro_400"
handler403 = "apps.core.views.erro_403"
handler404 = "apps.core.views.erro_404"
handler500 = "apps.core.views.erro_500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("conta/", include("apps.contas.urls")),
    path("organizacoes/", include("apps.organizacoes.urls")),
    path("regras/", include("apps.regras.urls")),
    path("candidaturas/", include("apps.candidaturas.urls")),
    path("documentos/", include("apps.documentos.urls")),
    path("workflow/", include("apps.workflow.urls")),
    path("financeiro/", include("apps.financeiro.urls")),
    path("", include("apps.core.urls")),
]
