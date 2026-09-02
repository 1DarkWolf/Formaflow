from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura
from apps.organizacoes.models import VinculoLaboral

from ..models import (
    Documento,
    EstadoDocumento,
    FaseDocumento,
    FicheiroArmazenado,
    RequisitoDocumento,
    SnapshotSubmissao,
    VersaoDocumento,
)
from ..services import (
    carregar_para_requisito,
    criar_snapshot,
    gerar_checklist_preparacao,
    substituir_documento,
    validar_versao,
)
from .factories import DocumentFixtureMixin, pdf_upload


class DocumentServiceTests(DocumentFixtureMixin, TestCase):
    def requirement(self, *, beneficiary=True):
        return RequisitoDocumento.objects.create(
            candidatura=self.application,
            beneficiario=self.beneficiary if beneficiary else None,
            tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
            fase=FaseDocumento.PREPARACAO,
            codigo_regra="RN-DOC-004",
        )

    def upload(self, requirement=None, *, file=None, user=None):
        return carregar_para_requisito(
            requisito_id=(requirement or self.requirement()).pk,
            ficheiro=file or pdf_upload(),
            utilizador=user or self.manager,
        )

    def test_dynamic_checklist_reflects_business_and_unemployment_conditions(self):
        created = gerar_checklist_preparacao(
            candidatura_id=self.application.pk, utilizador=self.manager
        )

        codes = {item.tipo_documento.codigo for item in created}
        self.assertEqual(
            codes,
            {
                "DOCUMENTO_EMPRESA",
                "IDENTIFICACAO_CIVIL",
                "SITUACAO_LABORAL",
                "TITULARIDADE_BANCARIA",
            },
        )
        self.assertFalse(
            self.application.requisitos_documentais.filter(
                tipo_documento__codigo="CURRICULO"
            ).exists()
        )
        self.assertEqual(
            gerar_checklist_preparacao(candidatura_id=self.application.pk, utilizador=self.manager),
            [],
        )

        unemployed_user = self.make_candidate(
            "desempregado.docs@example.test", "100000029", "Pessoa", "Desempregada"
        )
        unemployment = VinculoLaboral.objects.create(
            candidato=unemployed_user,
            situacao=VinculoLaboral.Situacao.DESEMPREGADO,
            inicio_em=timezone.localdate(),
            inscricao_iefp_em=timezone.localdate(),
        )
        individual = Candidatura.objects.create(
            tipo=Candidatura.Tipo.INDIVIDUAL,
            titular_candidato=unemployed_user,
            conjunto_regras=self.rules,
            criada_por=unemployed_user.utilizador,
        )
        BeneficiarioCandidatura.objects.create(
            candidatura=individual,
            candidato=unemployed_user,
            e_titular=True,
            situacao_referencia=VinculoLaboral.Situacao.DESEMPREGADO,
            vinculo_referencia=unemployment,
        )
        generated = gerar_checklist_preparacao(
            candidatura_id=individual.pk,
            utilizador=unemployed_user.utilizador,
        )
        individual_codes = {item.tipo_documento.codigo for item in generated}
        self.assertIn("CURRICULO", individual_codes)
        self.assertNotIn("DOCUMENTO_EMPRESA", individual_codes)

    def test_pdf_exactly_at_configured_limit_is_accepted(self):
        version = self.upload(file=pdf_upload(size=2 * 1024 * 1024))

        self.assertEqual(version.ficheiro.tamanho_bytes, 2 * 1024 * 1024)
        self.assertEqual(version.ficheiro.estado_upload, FicheiroArmazenado.EstadoUpload.CONCLUIDO)
        self.assertEqual(version.documento.estado_atual, EstadoDocumento.RECEBIDO)

    def test_one_byte_over_limit_is_rejected_without_records(self):
        requirement = self.requirement()

        with self.assertRaises(ValidationError):
            self.upload(requirement, file=pdf_upload(size=(2 * 1024 * 1024) + 1))

        self.assertFalse(Documento.objects.exists())
        self.assertFalse(VersaoDocumento.objects.exists())
        self.assertFalse(FicheiroArmazenado.objects.exists())
        requirement.refresh_from_db()
        self.assertEqual(requirement.estado, EstadoDocumento.EM_FALTA)

    def test_fake_pdf_is_blocked_by_content_signature(self):
        fake = pdf_upload()
        fake.file.seek(0)
        fake.file.truncate(0)
        fake.file.write(b"MZ executable content")
        fake.file.seek(0)
        fake.size = len(b"MZ executable content")

        with self.assertRaises(ValidationError):
            self.upload(file=fake)

        self.assertFalse(FicheiroArmazenado.objects.exists())

    def test_original_name_is_sanitized_and_storage_key_is_random(self):
        upload = pdf_upload(name="seguro.pdf")
        upload._name = "../../pasta\\segredo.pdf"

        version = self.upload(file=upload)

        self.assertEqual(version.ficheiro.nome_original, "segredo.pdf")
        self.assertNotIn("segredo", version.ficheiro.chave_armazenamento)
        self.assertTrue(version.ficheiro.chave_armazenamento.startswith("documentos/"))

    def test_replacement_keeps_history_and_exactly_one_current_version(self):
        version_one = self.upload()

        version_two = substituir_documento(
            documento_id=version_one.documento_id,
            ficheiro=pdf_upload("corrigido.pdf"),
            motivo="Corrigir a declaração.",
            utilizador=self.manager,
        )

        version_one.refresh_from_db()
        self.assertFalse(version_one.corrente)
        self.assertEqual(version_one.estado_validacao, VersaoDocumento.EstadoValidacao.SUBSTITUIDO)
        self.assertEqual(version_one.motivo_substituicao, "Corrigir a declaração.")
        self.assertTrue(version_two.corrente)
        self.assertEqual(version_two.numero, 2)
        self.assertEqual(
            VersaoDocumento.objects.filter(documento=version_one.documento, corrente=True).count(),
            1,
        )

    def test_database_rejects_two_current_versions(self):
        first = self.upload()
        stored = FicheiroArmazenado.objects.create(
            chave_armazenamento="documentos/test/second.pdf",
            nome_original="second.pdf",
            tipo_mime="application/pdf",
            tamanho_bytes=14,
            sha256="a" * 64,
            estado_upload=FicheiroArmazenado.EstadoUpload.CONCLUIDO,
            estado_seguranca=FicheiroArmazenado.EstadoSeguranca.SEGURO,
            carregado_por=self.manager,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            VersaoDocumento.objects.create(
                documento=first.documento,
                numero=2,
                ficheiro=stored,
                carregada_por=self.manager,
                corrente=True,
            )

    def test_snapshot_keeps_original_version_after_replacement(self):
        requirement = self.requirement()
        original = self.upload(requirement)
        validar_versao(
            versao_id=original.pk,
            utilizador=self.administrator,
            resultado=VersaoDocumento.EstadoValidacao.VALIDO,
        )
        snapshot = criar_snapshot(
            candidatura_id=self.application.pk,
            utilizador=self.manager,
            finalidade=SnapshotSubmissao.Finalidade.SUBMISSAO,
        )

        replacement = substituir_documento(
            documento_id=original.documento_id,
            ficheiro=pdf_upload("nova.pdf"),
            motivo="Atualização posterior.",
            utilizador=self.manager,
        )

        self.assertQuerySetEqual(snapshot.versoes_documentos.all(), [original])
        self.assertNotIn(replacement, snapshot.versoes_documentos.all())
        snapshot.dados = {"alterado": True}
        with self.assertRaises(ValidationError):
            snapshot.save()

    def test_storage_failure_does_not_leave_valid_database_records(self):
        requirement = self.requirement()
        with patch("apps.documentos.services.guardar_privado", side_effect=OSError("storage")):
            with self.assertRaises(OSError):
                self.upload(requirement)

        self.assertFalse(FicheiroArmazenado.objects.exists())
        self.assertFalse(VersaoDocumento.objects.exists())
        requirement.refresh_from_db()
        self.assertEqual(requirement.estado, EstadoDocumento.EM_FALTA)

    def test_invalid_validation_requires_observation_and_self_validation_is_forbidden(self):
        version = self.upload()
        with self.assertRaises(PermissionDenied):
            validar_versao(
                versao_id=version.pk,
                utilizador=self.manager,
                resultado=VersaoDocumento.EstadoValidacao.VALIDO,
            )
        with self.assertRaises(ValidationError):
            validar_versao(
                versao_id=version.pk,
                utilizador=self.administrator,
                resultado=VersaoDocumento.EstadoValidacao.INVALIDO,
            )

    def test_cross_application_relationships_and_invalid_dates_are_rejected(self):
        other = Candidatura.objects.create(
            tipo=Candidatura.Tipo.EMPRESARIAL,
            titular_empresa=self.company,
            conjunto_regras=self.rules,
            criada_por=self.manager,
        )
        requirement = RequisitoDocumento(
            candidatura=other,
            beneficiario=self.beneficiary,
            tipo_documento=self.document_types["IDENTIFICACAO_CIVIL"],
            fase=FaseDocumento.PREPARACAO,
        )
        with self.assertRaises(ValidationError):
            requirement.full_clean()

        version = self.upload()
        version.emitido_em = date(2026, 5, 2)
        version.valido_ate = date(2026, 5, 1)
        with self.assertRaises(ValidationError):
            version.full_clean()
