from django.urls import path

from . import views

app_name = "workflow"

urlpatterns = [
    path("<uuid:public_id>/", views.detalhe, name="detalhe"),
    path(
        "<uuid:public_id>/acontecimento/<str:codigo>/",
        views.acontecimento,
        name="acontecimento",
    ),
    path("<uuid:public_id>/pedidos/novo/", views.novo_pedido, name="novo_pedido"),
    path(
        "<uuid:public_id>/documentos/novo/",
        views.novo_documento,
        name="novo_documento",
    ),
    path("pedidos/<int:pedido_id>/", views.detalhe_pedido, name="detalhe_pedido"),
    path(
        "questoes/<int:questao_id>/rascunho/",
        views.guardar_resposta,
        name="guardar_resposta",
    ),
    path(
        "questoes/<int:questao_id>/documento/",
        views.novo_documento_questao,
        name="novo_documento_questao",
    ),
    path(
        "pedidos/<int:pedido_id>/resposta-completa/",
        views.resposta_completa,
        name="resposta_completa",
    ),
    path("<uuid:public_id>/decisao/", views.decisao, name="decisao"),
]
