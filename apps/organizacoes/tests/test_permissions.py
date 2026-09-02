from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contas.constants import GRUPO_ADMINISTRADOR
from apps.contas.models import PerfilCandidato, Utilizador
from apps.organizacoes.models import AssociacaoEmpresa, Empresa, VinculoLaboral
from apps.organizacoes.selectors import (
    empresas_visiveis_por,
    utilizador_pode_consultar_detalhes,
    utilizador_pode_gerir_empresa,
)

PASSWORD = "Segura!2026Projeto"


class OrganizationScopeTests(TestCase):
    def setUp(self):
        self.company_a = Empresa.objects.create(
            nipc="100000010",
            denominacao_legal="Empresa A, Lda.",
            email="interno-a@example.test",
        )
        self.company_b = Empresa.objects.create(
            nipc="100000029",
            denominacao_legal="Empresa B, Lda.",
            email="interno-b@example.test",
        )
        self.manager = Utilizador.objects.create_user(
            email="gestor@example.test",
            password=PASSWORD,
            nome_proprio="Gestor",
            apelido="A",
        )
        self.association = AssociacaoEmpresa.objects.create(
            utilizador=self.manager,
            empresa=self.company_a,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            inicio_em=timezone.now() - timedelta(days=1),
        )

    def test_manager_only_sees_associated_company(self):
        visible = empresas_visiveis_por(self.manager)

        self.assertQuerySetEqual(visible, [self.company_a])
        self.assertTrue(utilizador_pode_gerir_empresa(self.manager, self.company_a))
        self.assertFalse(utilizador_pode_gerir_empresa(self.manager, self.company_b))

        self.client.force_login(self.manager)
        response = self.client.get(reverse("organizacoes:lista_empresas"))
        self.assertContains(response, "Empresa A, Lda.")
        self.assertNotContains(response, "Empresa B, Lda.")

    def test_direct_url_for_other_company_returns_not_found(self):
        self.client.force_login(self.manager)

        allowed = self.client.get(
            reverse("organizacoes:detalhe_empresa", args=[self.company_a.public_id])
        )
        forbidden = self.client.get(
            reverse("organizacoes:detalhe_empresa", args=[self.company_b.public_id])
        )

        self.assertContains(allowed, "interno-a@example.test")
        self.assertEqual(forbidden.status_code, 404)

    def test_expired_association_immediately_removes_scope(self):
        self.association.fim_em = timezone.now() - timedelta(seconds=1)
        self.association.save()

        self.assertFalse(empresas_visiveis_por(self.manager).exists())

    def test_consultation_role_can_view_details_but_not_manage(self):
        self.association.papel = AssociacaoEmpresa.Papel.CONSULTA
        self.association.save()

        self.assertTrue(utilizador_pode_consultar_detalhes(self.manager, self.company_a))
        self.assertFalse(utilizador_pode_gerir_empresa(self.manager, self.company_a))

    def test_candidate_sees_only_company_identity_from_current_employment(self):
        candidate = Utilizador.objects.create_user(
            email="candidato@example.test",
            password=PASSWORD,
            nome_proprio="Candidato",
            apelido="A",
        )
        profile = PerfilCandidato.objects.create(
            utilizador=candidate,
            nif="100000002",
            data_nascimento=date(1994, 3, 2),
        )
        VinculoLaboral.objects.create(
            candidato=profile,
            empresa=self.company_a,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=timezone.localdate() - timedelta(days=30),
        )
        self.client.force_login(candidate)

        response = self.client.get(
            reverse("organizacoes:detalhe_empresa", args=[self.company_a.public_id])
        )

        self.assertContains(response, "Empresa A, Lda.")
        self.assertNotContains(response, self.company_a.nipc)
        self.assertNotContains(response, self.company_a.email)

    def test_administrator_group_sees_all_companies(self):
        administrator = Utilizador.objects.create_user(
            email="administrador@example.test",
            password=PASSWORD,
            nome_proprio="Administrador",
            apelido="Global",
        )
        administrator.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))

        self.assertCountEqual(
            empresas_visiveis_por(administrator), [self.company_a, self.company_b]
        )
        self.assertTrue(utilizador_pode_consultar_detalhes(administrator, self.company_b))
        self.assertTrue(utilizador_pode_gerir_empresa(administrator, self.company_b))

    def test_inactive_user_has_no_organization_scope(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        self.assertFalse(empresas_visiveis_por(self.manager).exists())
        self.assertFalse(utilizador_pode_gerir_empresa(self.manager, self.company_a))

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(reverse("organizacoes:lista_empresas"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("contas:login"), response.url)
