import hashlib
import hmac

from django.conf import settings

from .models import RegistoAuditoria

METADADOS_PERMITIDOS = {
    "candidatura_public_id",
    "estado",
    "filtros",
    "formato",
    "quantidade",
}


def _hash_ip(request):
    if not request:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    address = forwarded.split(",", 1)[0] if forwarded else request.META.get("REMOTE_ADDR", "")
    if not address:
        return ""
    return hmac.new(
        settings.DATA_HASH_KEY.encode(),
        address.strip().encode(),
        hashlib.sha256,
    ).hexdigest()


def registar_evento(
    *,
    acao,
    tipo_objeto,
    utilizador=None,
    resultado=RegistoAuditoria.Resultado.SUCESSO,
    id_objeto="",
    public_id_objeto=None,
    metadados=None,
    request=None,
):
    dados_seguros = {
        key: value for key, value in (metadados or {}).items() if key in METADADOS_PERMITIDOS
    }
    return RegistoAuditoria.objects.create(
        utilizador=utilizador if getattr(utilizador, "is_authenticated", False) else None,
        acao=acao.strip().upper(),
        tipo_objeto=tipo_objeto.strip(),
        id_objeto=str(id_objeto or ""),
        public_id_objeto=public_id_objeto,
        resultado=resultado,
        id_pedido=(request.headers.get("X-Request-ID", "")[:100] if request else ""),
        hash_ip=_hash_ip(request),
        metadados=dados_seguros,
    )
