import hashlib
import hmac
import re

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ValidationError


def normalizar_iban(value):
    return re.sub(r"\s+", "", str(value or "")).upper()


def validar_iban(value):
    iban = normalizar_iban(value)
    if not 15 <= len(iban) <= 34 or not iban.isalnum() or not iban[:2].isalpha():
        raise ValidationError("Introduza um IBAN válido.")

    rearranged = f"{iban[4:]}{iban[:4]}"
    numeric = "".join(str(int(character, 36)) for character in rearranged)
    if int(numeric) % 97 != 1:
        raise ValidationError("Introduza um IBAN válido.")
    return iban


def cifrar_iban(iban):
    normalized = validar_iban(iban)
    return Fernet(settings.DATA_ENCRYPTION_KEY.encode()).encrypt(normalized.encode()).decode()


def decifrar_iban(ciphertext):
    return Fernet(settings.DATA_ENCRYPTION_KEY.encode()).decrypt(ciphertext.encode()).decode()


def calcular_hash_iban(iban):
    normalized = validar_iban(iban)
    return hmac.new(
        settings.DATA_HASH_KEY.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()
