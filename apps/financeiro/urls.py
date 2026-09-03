from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("<uuid:public_id>/", views.detalhe_financeiro, name="detalhe"),
    path("<uuid:public_id>/calcular/", views.calcular, name="calcular"),
    path("<uuid:public_id>/confirmar/", views.confirmar, name="confirmar"),
    path("<uuid:public_id>/movimento/", views.movimento, name="movimento"),
    path("<uuid:public_id>/risco/", views.risco, name="risco"),
    path("<uuid:public_id>/restituicao/", views.restituicao, name="restituicao"),
    path(
        "<uuid:public_id>/restituicao/regularizar/",
        views.regularizar_restituicao,
        name="regularizar_restituicao",
    ),
]
