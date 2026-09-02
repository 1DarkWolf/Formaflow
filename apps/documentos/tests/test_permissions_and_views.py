from django.test import TestCase
from django.urls import reverse

from apps.candidaturas.services import adicionar_beneficiario
from apps.organizacoes.models import VinculoLaboral

from ..models import FaseDocumento, RequisitoDocumento
from ..services import carregar_para_requisito, gerar_checklist_preparacao
from .factories import DocumentFixtureMixin, pdf_upload


class DocumentPermissionAndViewTests(DocumentFixtureMixin, TestCase):
    def requirement(self, beneficiary=None):
        return RequisitoDocumento.objects.create(
            candidatura=self.application,
            beneficiario=beneficiary or self.beneficiary,
            tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
            fase=FaseDocumento.PREPARACAO,
            codigo_regra="RN-DOC-004",
        )

    def test_checklist_screen_generates_requirements_and_explains_scope(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("documentos:gerar_checklist", args=[self.application.public_id])
        )

        self.assertRedirects(
            response,
            reverse("documentos:checklist", args=[self.application.public_id]),
        )
        page = self.client.get(reverse("documentos:checklist", args=[self.application.public_id]))
        self.assertContains(page, "Checklist documental")
        self.assertContains(page, "Identificacao Civil")
        self.assertContains(page, "RN-DOC-004")
        self.assertContains(page, self.candidate.utilizador.get_full_name())

    def test_upload_and_authorized_download_use_private_endpoint_and_headers(self):
        requirement = self.requirement()
        self.client.force_login(self.manager)
        upload_response = self.client.post(
            reverse("documentos:carregar", args=[requirement.pk]),
            data={"ficheiro": pdf_upload("prova.pdf"), "titulo": "Prova"},
        )
        document = requirement.documentos.get()
        version = document.versoes.get()

        self.assertRedirects(
            upload_response,
            reverse("documentos:checklist", args=[self.application.public_id]),
        )
        with self.assertLogs("formaflow.documentos", level="INFO") as logs:
            response = self.client.get(
                reverse("documentos:descarregar", args=[document.public_id, version.numero])
            )
            body = b"".join(response.streaming_content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body.startswith(b"%PDF-"))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertNotIn(
            version.ficheiro.chave_armazenamento, response.url if hasattr(response, "url") else ""
        )
        self.assertIn("document_download autorizado", logs.output[0])

    def test_unauthorized_direct_download_is_not_found_and_reveals_no_metadata(self):
        requirement = self.requirement()
        version = carregar_para_requisito(
            requisito_id=requirement.pk,
            ficheiro=pdf_upload("segredo.pdf"),
            utilizador=self.manager,
        )
        self.client.force_login(self.outsider)

        response = self.client.get(
            reverse(
                "documentos:descarregar",
                args=[version.documento.public_id, version.numero],
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "segredo.pdf", status_code=404)
        self.assertNotContains(
            response,
            version.ficheiro.chave_armazenamento,
            status_code=404,
        )

    def test_candidate_only_sees_and_downloads_own_business_documents(self):
        colleague = self.make_candidate(
            "colega.docs@example.test", "100000029", "Colega", "Privado"
        )
        VinculoLaboral.objects.create(
            candidato=colleague,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=self.employment.inicio_em,
        )
        colleague_beneficiary = adicionar_beneficiario(
            candidatura_id=self.application.pk,
            candidato=colleague,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        own_requirement = self.requirement()
        colleague_requirement = self.requirement(colleague_beneficiary)
        own_version = carregar_para_requisito(
            requisito_id=own_requirement.pk,
            ficheiro=pdf_upload("meu.pdf"),
            utilizador=self.manager,
        )
        colleague_version = carregar_para_requisito(
            requisito_id=colleague_requirement.pk,
            ficheiro=pdf_upload("colega.pdf"),
            utilizador=self.manager,
        )
        self.client.force_login(self.candidate.utilizador)

        page = self.client.get(reverse("documentos:checklist", args=[self.application.public_id]))
        denied = self.client.get(
            reverse(
                "documentos:descarregar",
                args=[colleague_version.documento.public_id, colleague_version.numero],
            )
        )
        allowed = self.client.get(
            reverse(
                "documentos:descarregar",
                args=[own_version.documento.public_id, own_version.numero],
            )
        )

        self.assertContains(page, "meu.pdf")
        self.assertNotContains(page, "colega.pdf")
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(allowed.status_code, 200)

    def test_candidate_can_upload_own_requested_document_but_not_a_colleagues(self):
        colleague = self.make_candidate(
            "colega.upload@example.test", "100000029", "Colega", "Upload"
        )
        VinculoLaboral.objects.create(
            candidato=colleague,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=self.employment.inicio_em,
        )
        colleague_beneficiary = adicionar_beneficiario(
            candidatura_id=self.application.pk,
            candidato=colleague,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        own_requirement = self.requirement()
        colleague_requirement = self.requirement(colleague_beneficiary)
        self.client.force_login(self.candidate.utilizador)

        own_response = self.client.post(
            reverse("documentos:carregar", args=[own_requirement.pk]),
            data={"ficheiro": pdf_upload("meu-upload.pdf")},
        )
        denied_response = self.client.post(
            reverse("documentos:carregar", args=[colleague_requirement.pk]),
            data={"ficheiro": pdf_upload("alheio.pdf")},
        )

        self.assertEqual(own_response.status_code, 302)
        self.assertTrue(own_requirement.documentos.exists())
        self.assertEqual(denied_response.status_code, 404)
        self.assertFalse(colleague_requirement.documentos.exists())

    def test_invalid_upload_view_returns_error_without_creating_document(self):
        requirement = self.requirement()
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("documentos:carregar", args=[requirement.pk]),
            data={"ficheiro": pdf_upload("errado.txt")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "extensão .pdf", status_code=400)
        self.assertFalse(requirement.documentos.exists())

    def test_snapshot_view_refuses_incomplete_blocking_checklist(self):
        gerar_checklist_preparacao(candidatura_id=self.application.pk, utilizador=self.manager)
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("documentos:snapshot", args=[self.application.public_id]),
            data={"finalidade": "SUBMISSAO"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "requisitos documentais bloqueantes", status_code=400)

    def test_document_endpoints_require_authentication(self):
        response = self.client.get(
            reverse("documentos:checklist", args=[self.application.public_id])
        )

        self.assertEqual(response.status_code, 302)
