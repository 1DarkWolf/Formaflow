from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from apps.candidaturas.services import adicionar_beneficiario, criar_candidatura_empresarial
from apps.contas.models import PerfilCandidato, Utilizador
from apps.organizacoes.models import AssociacaoEmpresa, Empresa, VinculoLaboral
from apps.regras.models import ConjuntoRegras, ParametroRegra, TipoDocumento
from apps.regras.services import publicar_conjunto

PASSWORD = "Segura!2026Projeto"
IN_MEMORY_STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


def pdf_upload(name="documento.pdf", size=None):
    prefix = b"%PDF-1.4\n"
    suffix = b"%%EOF"
    if size is None:
        payload = prefix + b"1 0 obj<</Type/Catalog>>endobj\n" + suffix
    else:
        payload = prefix + (b"0" * (size - len(prefix) - len(suffix))) + suffix
    return SimpleUploadedFile(name, payload, content_type="application/pdf")


class DocumentFixtureMixin:
    storage_override = override_settings(STORAGES=IN_MEMORY_STORAGE)

    @classmethod
    def setUpClass(cls):
        cls.storage_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.storage_override.disable()

    def setUp(self):
        self.administrator = Utilizador.objects.create_superuser(
            email="admin.docs@example.test",
            password=PASSWORD,
            nome_proprio="Admin",
            apelido="Documentos",
        )
        self.manager = self.make_user("gestor.docs@example.test", "Gestor", "Documentos")
        self.outsider = self.make_user("fora.docs@example.test", "Fora", "Âmbito")
        self.candidate = self.make_candidate(
            "candidato.docs@example.test", "100000002", "Candidato", "Documentos"
        )
        self.company = Empresa.objects.create(
            nipc="100000010", denominacao_legal="Empresa Documental, Lda."
        )
        AssociacaoEmpresa.objects.create(
            utilizador=self.manager,
            empresa=self.company,
            papel=AssociacaoEmpresa.Papel.GESTOR,
            inicio_em=timezone.now() - timedelta(days=1),
        )
        self.employment = VinculoLaboral.objects.create(
            candidato=self.candidate,
            empresa=self.company,
            situacao=VinculoLaboral.Situacao.CONTA_OUTREM,
            inicio_em=timezone.localdate() - timedelta(days=30),
        )
        self.rules = ConjuntoRegras.objects.create(
            codigo="DOCS",
            versao=1,
            designacao="Regras documentais",
            vigente_desde=date(2026, 1, 1),
            fonte="Teste",
        )
        for code, value, unit in (
            ("CFG-EMPRESA-BENEFICIARIOS", 20, "trabalhadores"),
            ("CFG-FICHEIRO-TAMANHO", 2, "MB"),
        ):
            ParametroRegra.objects.create(
                conjunto_regras=self.rules,
                codigo=code,
                designacao=code,
                tipo_valor=ParametroRegra.TipoValor.INTEIRO,
                valor=value,
                unidade=unit,
            )
        publicar_conjunto(self.rules.pk, self.administrator)
        self.rules.refresh_from_db()
        type_specs = {
            "DOCUMENTO_EMPRESA": TipoDocumento.Categoria.EMPRESA,
            "IDENTIFICACAO_CIVIL": TipoDocumento.Categoria.IDENTIDADE,
            "SITUACAO_LABORAL": TipoDocumento.Categoria.EMPREGO,
            "CURRICULO": TipoDocumento.Categoria.EMPREGO,
            "DECLARACAO_FORMADORA": TipoDocumento.Categoria.FORMACAO,
            "TITULARIDADE_BANCARIA": TipoDocumento.Categoria.FINANCEIRO,
        }
        self.document_types = {
            code: TipoDocumento.objects.create(
                codigo=code,
                designacao=code.replace("_", " ").title(),
                categoria=category,
                sensibilidade=TipoDocumento.Sensibilidade.PESSOAL,
            )
            for code, category in type_specs.items()
        }
        self.application = criar_candidatura_empresarial(
            criada_por=self.manager,
            titular_empresa=self.company,
            conjunto_regras=self.rules,
        )
        self.beneficiary = adicionar_beneficiario(
            candidatura_id=self.application.pk,
            candidato=self.candidate,
            utilizador=self.manager,
            versao_esperada=self.application.versao,
        )
        self.application.refresh_from_db()

    @staticmethod
    def make_user(email, first_name, last_name):
        return Utilizador.objects.create_user(
            email=email,
            password=PASSWORD,
            nome_proprio=first_name,
            apelido=last_name,
        )

    def make_candidate(self, email, nif, first_name, last_name):
        user = self.make_user(email, first_name, last_name)
        return PerfilCandidato.objects.create(
            utilizador=user,
            nif=nif,
            data_nascimento=date(1992, 4, 2),
        )
