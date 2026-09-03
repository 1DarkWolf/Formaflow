from .models import Notificacao


def avisos_cabecalho(request):
    if not request.user.is_authenticated:
        return {"avisos_nao_lidos": 0}
    return {
        "avisos_nao_lidos": request.user.notificacoes.filter(
            estado__in=(
                Notificacao.Estado.PENDENTE,
                Notificacao.Estado.ENVIADA,
                Notificacao.Estado.FALHOU,
            )
        ).count()
    }
