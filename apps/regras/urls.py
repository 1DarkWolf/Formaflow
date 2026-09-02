from django.urls import path

from . import views

app_name = "regras"

urlpatterns = [
    path("", views.lista_conjuntos, name="lista_conjuntos"),
    path("<int:conjunto_id>/publicar/", views.publicar, name="publicar"),
]
