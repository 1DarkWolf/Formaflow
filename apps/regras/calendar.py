from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Feriado


def adicionar_dias_consecutivos(data_inicial, quantidade):
    if quantidade < 0:
        raise ValidationError("A quantidade de dias não pode ser negativa.")
    return data_inicial + timedelta(days=quantidade)


def adicionar_dias_uteis(data_inicial, quantidade, *, incluir_inicial=False, regiao=""):
    if quantidade < 0:
        raise ValidationError("A quantidade de dias não pode ser negativa.")
    if quantidade == 0:
        return data_inicial

    normalized_region = regiao.strip().upper()
    current = data_inicial if incluir_inicial else data_inicial + timedelta(days=1)
    counted = 0
    while counted < quantidade:
        if _dia_util(current, normalized_region):
            counted += 1
            if counted == quantidade:
                return current
        current += timedelta(days=1)

    raise RuntimeError("Não foi possível calcular a data útil.")


def _dia_util(day, region):
    if day.weekday() >= 5:
        return False

    applicable_holiday = Feriado.objects.filter(ativo=True, data=day).filter(
        Q(ambito=Feriado.Ambito.NACIONAL)
        | Q(ambito__in=(Feriado.Ambito.REGIONAL, Feriado.Ambito.MUNICIPAL), regiao=region)
    )
    return not applicable_holiday.exists()
