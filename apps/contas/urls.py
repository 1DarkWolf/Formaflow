from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import FormularioAutenticacao

app_name = "contas"

urlpatterns = [
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="contas/login.html",
            authentication_form=FormularioAutenticacao,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "sair/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("registar/", views.registar, name="registar"),
    path("registar/concluido/", views.registo_concluido, name="registo_concluido"),
    path("ativar/<uidb64>/<token>/", views.ativar, name="ativar"),
    path(
        "recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="contas/password_reset_form.html",
            email_template_name="contas/emails/password_reset.txt",
            subject_template_name="contas/emails/password_reset_subject.txt",
            success_url=reverse_lazy("contas:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="contas/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "repor/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="contas/password_reset_confirm.html",
            success_url=reverse_lazy("contas:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "repor/concluido/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="contas/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path(
        "seguranca/palavra-passe/",
        auth_views.PasswordChangeView.as_view(
            template_name="contas/password_change_form.html",
            success_url=reverse_lazy("contas:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "seguranca/palavra-passe/concluida/",
        auth_views.PasswordChangeDoneView.as_view(template_name="contas/password_change_done.html"),
        name="password_change_done",
    ),
    path("painel/", views.dashboard, name="dashboard"),
]
