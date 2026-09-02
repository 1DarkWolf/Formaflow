from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.regras.calendar import adicionar_dias_consecutivos, adicionar_dias_uteis
from apps.regras.models import Feriado


class CalendarTests(TestCase):
    def setUp(self):
        Feriado.objects.create(
            data=date(2026, 4, 27),
            designacao="Feriado nacional de teste",
            ambito=Feriado.Ambito.NACIONAL,
        )
        Feriado.objects.create(
            data=date(2026, 4, 29),
            designacao="Feriado regional de teste",
            ambito=Feriado.Ambito.REGIONAL,
            regiao="VISEU",
        )

    def test_business_days_skip_weekend_and_national_holiday(self):
        result = adicionar_dias_uteis(date(2026, 4, 24), 1)

        self.assertEqual(result, date(2026, 4, 28))

    def test_regional_holiday_only_applies_to_matching_region(self):
        self.assertEqual(
            adicionar_dias_uteis(date(2026, 4, 24), 2, regiao="viseu"),
            date(2026, 4, 30),
        )
        self.assertEqual(
            adicionar_dias_uteis(date(2026, 4, 24), 2, regiao="porto"),
            date(2026, 4, 29),
        )

    def test_initial_day_and_zero_boundary_are_explicit(self):
        start = date(2026, 4, 28)

        self.assertEqual(adicionar_dias_uteis(start, 1, incluir_inicial=True), start)
        self.assertEqual(adicionar_dias_uteis(start, 0), start)

    def test_consecutive_days_include_weekend(self):
        self.assertEqual(
            adicionar_dias_consecutivos(date(2026, 4, 24), 3),
            date(2026, 4, 27),
        )

    def test_negative_days_are_rejected(self):
        with self.assertRaises(ValidationError):
            adicionar_dias_uteis(date(2026, 4, 24), -1)
        with self.assertRaises(ValidationError):
            adicionar_dias_consecutivos(date(2026, 4, 24), -1)

    def test_non_national_holiday_requires_region(self):
        holiday = Feriado(
            data=date(2026, 5, 1),
            designacao="Regional incompleto",
            ambito=Feriado.Ambito.REGIONAL,
        )

        with self.assertRaises(ValidationError):
            holiday.full_clean()

    def test_national_holiday_clears_region_and_has_readable_name(self):
        holiday = Feriado(
            data=date(2026, 6, 10),
            designacao="Dia de Portugal",
            ambito=Feriado.Ambito.NACIONAL,
            regiao="Viseu",
        )

        holiday.full_clean()

        self.assertEqual(holiday.regiao, "")
        self.assertIn("Dia de Portugal", str(holiday))
