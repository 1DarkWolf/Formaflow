from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import token_ativacao_conta


def enviar_email_ativacao(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_ativacao_conta.make_token(user)
    caminho = reverse("contas:ativar", kwargs={"uidb64": uid, "token": token})
    contexto = {
        "nome": user.get_short_name(),
        "url_ativacao": request.build_absolute_uri(caminho),
    }
    mensagem = render_to_string("contas/emails/ativacao.txt", contexto)
    send_mail(
        subject="Ative a sua conta Forma Flow",
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
