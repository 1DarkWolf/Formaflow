from datetime import date

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.contas.constants import GRUPO_ADMINISTRADOR
from apps.contas.models import Utilizador
from apps.regras.models import ConjuntoRegras, ParametroRegra
from apps.regras.services import conjunto_aplicavel, publicar_conjunto

PASSWORD = "Segura!2026Projeto"


class RulePublishingTests(TestCase):
    def setUp(self):
        self.administrator = Utilizador.objects.create_user(
            email="admin.regras@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Regras",
        )
        self.administrator.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
        self.manager = Utilizador.objects.create_user(
            email="gestor.regras@example.test",
            password=PASSWORD,
            nome_proprio="Gestor",
            apelido="Regras",
        )
        self.rules = ConjuntoRegras.objects.create(
            codigo=" cheque_formacao ",
            versao=1,
            designacao="Regras de teste",
            vigente_desde=date(2026, 1, 1),
            vigente_ate=date(2026, 12, 31),
            fonte="Fonte académica de teste",
        )
        self.parameter = ParametroRegra.objects.create(
            conjunto_regras=self.rules,
            codigo=" cfg-idade-min ",
            designacao="Idade mínima",
            tipo_valor=ParametroRegra.TipoValor.INTEIRO,
            valor=16,
            unidade="anos",
        )

    def test_codes_are_normalized(self):
        self.assertEqual(self.rules.codigo, "CHEQUE_FORMACAO")
        self.assertEqual(self.parameter.codigo, "CFG-IDADE-MIN")
        self.assertEqual(str(self.rules), "CHEQUE_FORMACAO v1")
        self.assertIn("CFG-IDADE-MIN", str(self.parameter))

    def test_only_administrator_can_publish(self):
        with self.assertRaises(PermissionDenied):
            publicar_conjunto(self.rules.pk, self.manager)

        published = publicar_conjunto(self.rules.pk, self.administrator)

        self.assertEqual(published.estado, ConjuntoRegras.Estado.ATIVO)
        self.assertIsNotNone(published.publicado_em)
        self.assertEqual(published.publicado_por, self.administrator)

    def test_published_rules_and_parameters_are_immutable(self):
        published = publicar_conjunto(self.rules.pk, self.administrator)
        published.designacao = "Tentativa de alteração"

        with self.assertRaises(ValidationError):
            published.save()
        with self.assertRaises(ValidationError):
            published.delete()

        self.parameter.valor = 18
        with self.assertRaises(ValidationError):
            self.parameter.save()
        with self.assertRaises(ValidationError):
            self.parameter.delete()

        with self.assertRaises(ValidationError):
            self.rules.delete()

    def test_publishing_same_version_twice_is_rejected(self):
        publicar_conjunto(self.rules.pk, self.administrator)

        with self.assertRaises(ValidationError):
            publicar_conjunto(self.rules.pk, self.administrator)

    def test_overlapping_published_period_is_rejected(self):
        publicar_conjunto(self.rules.pk, self.administrator)
        overlapping = ConjuntoRegras.objects.create(
            codigo="CHEQUE_FORMACAO",
            versao=2,
            designacao="Regras sobrepostas",
            vigente_desde=date(2026, 6, 1),
            fonte="Fonte de teste",
        )

        with self.assertRaises(ValidationError):
            publicar_conjunto(overlapping.pk, self.administrator)

    def test_applicable_rules_follow_reference_date(self):
        publicar_conjunto(self.rules.pk, self.administrator)

        self.assertEqual(conjunto_aplicavel("cheque_formacao", date(2026, 6, 1)), self.rules)
        self.assertIsNone(conjunto_aplicavel("CHEQUE_FORMACAO", date(2027, 1, 1)))

    def test_invalid_parameter_type_blocks_publication(self):
        self.parameter.valor = True
        self.parameter.save()

        with self.assertRaises(ValidationError) as error:
            publicar_conjunto(self.rules.pk, self.administrator)

        self.assertIn("valor", error.exception.message_dict)


class ParameterTypeTests(TestCase):
    def setUp(self):
        self.rules = ConjuntoRegras.objects.create(
            codigo="TIPOS",
            versao=1,
            designacao="Tipos de parâmetros",
            vigente_desde=date(2026, 1, 1),
            fonte="Teste",
        )

    def parameter(self, value_type, value):
        return ParametroRegra(
            conjunto_regras=self.rules,
            codigo=f"CFG-{value_type}",
            designacao="Parâmetro de teste",
            tipo_valor=value_type,
            valor=value,
        )

    def test_supported_parameter_types_are_validated(self):
        valid_cases = (
            (ParametroRegra.TipoValor.INTEIRO, 2),
            (ParametroRegra.TipoValor.DECIMAL, "4.25"),
            (ParametroRegra.TipoValor.BOOLEANO, True),
            (ParametroRegra.TipoValor.TEXTO, "valor"),
            (ParametroRegra.TipoValor.DATA, "2026-09-02"),
            (ParametroRegra.TipoValor.JSON, {"limites": [1, 2]}),
        )
        for value_type, value in valid_cases:
            with self.subTest(value_type=value_type):
                self.parameter(value_type, value).full_clean()

    def test_mismatched_parameter_types_are_rejected(self):
        invalid_cases = (
            (ParametroRegra.TipoValor.INTEIRO, True),
            (ParametroRegra.TipoValor.DECIMAL, False),
            (ParametroRegra.TipoValor.DECIMAL, "não decimal"),
            (ParametroRegra.TipoValor.BOOLEANO, 1),
            (ParametroRegra.TipoValor.TEXTO, 2),
            (ParametroRegra.TipoValor.DATA, "02/09/2026"),
            (ParametroRegra.TipoValor.DATA, 20260902),
            (ParametroRegra.TipoValor.JSON, "{}"),
        )
        for value_type, value in invalid_cases:
            with self.subTest(value_type=value_type), self.assertRaises(ValidationError):
                self.parameter(value_type, value).full_clean()

    def test_invalid_rule_period_is_rejected(self):
        self.rules.vigente_ate = date(2025, 12, 31)

        with self.assertRaises(ValidationError):
            self.rules.full_clean()

    def test_draft_rules_and_parameters_can_be_deleted(self):
        parameter = self.parameter(ParametroRegra.TipoValor.TEXTO, "temporário")
        parameter.save()
        parameter.delete()
        rules_id = self.rules.pk

        self.rules.delete()

        self.assertFalse(ConjuntoRegras.objects.filter(pk=rules_id).exists())
