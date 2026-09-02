from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_GET, require_http_methods, require_safe

from .emails import enviar_email_ativacao
from .forms import FormularioRegistoCandidato
from .models import Utilizador
from .tokens import token_ativacao_conta


@require_http_methods(["GET", "POST"])
def registar(request):
    if request.user.is_authenticated:
        return redirect("contas:dashboard")

    form = FormularioRegistoCandidato(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            enviar_email_ativacao(request, user)
        return redirect("contas:registo_concluido")

    return render(request, "contas/registar.html", {"form": form})


@require_safe
def registo_concluido(request):
    return render(request, "contas/registo_concluido.html")


@require_GET
def ativar(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = Utilizador.objects.filter(pk=user_id).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    token_valido = (
        user is not None and not user.is_active and token_ativacao_conta.check_token(user, token)
    )
    if not token_valido:
        return render(request, "contas/ativacao_invalida.html", status=400)

    user.is_active = True
    user.save(update_fields=["is_active", "atualizado_em"])
    messages.success(request, "A conta foi ativada. Já pode iniciar sessão.")
    return redirect("contas:login")


@login_required
@require_safe
def dashboard(request):
    papeis = list(request.user.groups.order_by("name").values_list("name", flat=True))
    if request.user.is_superuser and "Administrador" not in papeis:
        papeis.insert(0, "Administrador")
    return render(request, "contas/dashboard.html", {"papeis": papeis})
