from .models import Notificacao


def avisos_cabecalho(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"avisos_nao_lidos": 0}
    return {
        "avisos_nao_lidos": user.notificacoes.filter(
            estado__in=(
                Notificacao.Estado.PENDENTE,
                Notificacao.Estado.ENVIADA,
                Notificacao.Estado.FALHOU,
            )
        ).count()
    }
