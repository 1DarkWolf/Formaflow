from django.urls import path

from . import views

app_name = "candidaturas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("<uuid:public_id>/", views.detalhe, name="detalhe"),
    path(
        "<uuid:public_id>/beneficiarios/adicionar/",
        views.adicionar_beneficiario_view,
        name="adicionar_beneficiario",
    ),
    path(
        "<uuid:public_id>/formacao/adicionar/",
        views.adicionar_formacao_view,
        name="adicionar_formacao",
    ),
    path(
        "<uuid:public_id>/conta-pagamento/",
        views.definir_conta_view,
        name="definir_conta",
    ),
    path("<uuid:public_id>/verificar/", views.verificar, name="verificar"),
]
