from django.urls import path

from . import views

app_name = "documentos"

urlpatterns = [
    path("candidatura/<uuid:public_id>/", views.checklist_view, name="checklist"),
    path(
        "candidatura/<uuid:public_id>/gerar/",
        views.gerar_checklist_view,
        name="gerar_checklist",
    ),
    path(
        "candidatura/<uuid:public_id>/snapshot/",
        views.snapshot_view,
        name="snapshot",
    ),
    path("requisito/<int:requisito_id>/carregar/", views.carregar_view, name="carregar"),
    path("requisito/<int:requisito_id>/dispensar/", views.dispensar_view, name="dispensar"),
    path("<uuid:public_id>/historico/", views.historico_view, name="historico"),
    path("<uuid:public_id>/substituir/", views.substituir_view, name="substituir"),
    path(
        "<uuid:public_id>/versao/<int:numero>/descarregar/",
        views.descarregar_view,
        name="descarregar",
    ),
    path("versao/<int:versao_id>/validar/", views.validar_view, name="validar"),
]
