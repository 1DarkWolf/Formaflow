from django.urls import path

from . import views

app_name = "organizacoes"

urlpatterns = [
    path("empresas/", views.lista_empresas, name="lista_empresas"),
    path("empresas/<uuid:public_id>/", views.detalhe_empresa, name="detalhe_empresa"),
]
