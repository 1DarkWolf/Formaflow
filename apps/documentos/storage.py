import hashlib
import re
import uuid
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename

PDF_MIME = "application/pdf"


def sanitizar_nome(nome):
    """Return a display-only name without accepting path components."""
    leaf = str(nome or "documento.pdf").replace("\\", "/").rsplit("/", 1)[-1]
    leaf = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip()
    safe = get_valid_filename(leaf) or "documento.pdf"
    return safe[-255:]


def validar_pdf(upload, limite_bytes):
    if not upload:
        raise ValidationError("Selecione um ficheiro PDF.")
    name = sanitizar_nome(upload.name)
    if PurePosixPath(name).suffix.lower() != ".pdf":
        raise ValidationError("O ficheiro deve ter a extensão .pdf.")
    declared_size = getattr(upload, "size", None)
    if declared_size is not None and declared_size > limite_bytes:
        raise ValidationError(f"O ficheiro excede o limite de {limite_bytes} bytes.")
    payload = upload.read(limite_bytes + 1)
    if len(payload) > limite_bytes:
        raise ValidationError(f"O ficheiro excede o limite de {limite_bytes} bytes.")
    if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-1024:]:
        raise ValidationError("O conteúdo do ficheiro não corresponde a um PDF válido.")
    return {
        "conteudo": payload,
        "nome_original": name,
        "tipo_mime": PDF_MIME,
        "tamanho_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def guardar_privado(payload):
    key = f"documentos/{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex}.pdf"
    return default_storage.save(key, ContentFile(payload))


def eliminar_privado(chave):
    if chave:
        default_storage.delete(chave)
