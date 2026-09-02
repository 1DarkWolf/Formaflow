import re

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def normalizar_nif(value):
    """Remove common visual separators while preserving invalid characters."""
    return re.sub(r"[\s.-]", "", str(value or ""))


def validar_nif(value):
    """Validate the length and check digit used by Portuguese NIF numbers."""
    nif = normalizar_nif(value)
    if len(nif) != 9 or not nif.isdigit():
        raise ValidationError(_("O NIF deve conter exatamente nove algarismos."))

    weighted_sum = sum(
        int(digit) * weight for digit, weight in zip(nif[:8], range(9, 1, -1), strict=True)
    )
    check_digit = 11 - (weighted_sum % 11)
    if check_digit >= 10:
        check_digit = 0

    if check_digit != int(nif[-1]):
        raise ValidationError(_("Introduza um NIF válido."))


def validar_data_nao_futura(value):
    if value > timezone.localdate():
        raise ValidationError(_("A data de nascimento não pode estar no futuro."))
