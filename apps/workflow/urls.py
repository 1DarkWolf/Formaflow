from django.urls import path

from . import views

app_name = "workflow"

urlpatterns = [
    path("notificacoes/", views.notificacoes, name="notificacoes"),
    path(
        "notificacoes/<int:notificacao_id>/ler/",
        views.ler_notificacao,
        name="ler_notificacao",
    ),
    path(
        "notificacoes/<int:notificacao_id>/resolver/",
        views.resolver_aviso,
        name="resolver_aviso",
    ),
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
    path("<uuid:public_id>/termo/", views.termo, name="termo"),
    path(
        "participacoes/<int:participacao_id>/",
        views.participacao,
        name="participacao",
    ),
    path(
        "<uuid:public_id>/encerramento/iniciar/",
        views.iniciar_encerramento,
        name="iniciar_encerramento",
    ),
    path(
        "<uuid:public_id>/encerramento/submeter/",
        views.submissao_encerramento,
        name="submissao_encerramento",
    ),
    path(
        "<uuid:public_id>/encerramento/concluir/",
        views.conclusao_encerramento,
        name="conclusao_encerramento",
    ),
    path(
        "<uuid:public_id>/encerramento/regularizar/",
        views.regularizacao_financeira,
        name="regularizacao_financeira",
    ),
    path(
        "<uuid:public_id>/correcao/",
        views.correcao_terminal,
        name="correcao_terminal",
    ),
]
