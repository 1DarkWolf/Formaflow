import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def normalizar_nipc(value):
    return re.sub(r"[\s.-]", "", str(value or ""))


def validar_nipc(value):
    nipc = normalizar_nipc(value)
    if len(nipc) != 9 or not nipc.isdigit():
        raise ValidationError(_("O NIPC deve conter exatamente nove algarismos."))

    weighted_sum = sum(
        int(digit) * weight for digit, weight in zip(nipc[:8], range(9, 1, -1), strict=True)
    )
    check_digit = 11 - (weighted_sum % 11)
    if check_digit >= 10:
        check_digit = 0
    if check_digit != int(nipc[-1]):
        raise ValidationError(_("Introduza um NIPC válido."))
