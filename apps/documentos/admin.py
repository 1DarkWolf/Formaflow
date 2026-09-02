from django.contrib import admin

from .models import (
    Documento,
    FicheiroArmazenado,
    RequisitoDocumento,
    SnapshotSubmissao,
    VersaoDocumento,
)


class SemEliminacaoAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FicheiroArmazenado)
class FicheiroArmazenadoAdmin(SemEliminacaoAdmin):
    list_display = (
        "nome_original",
        "tipo_mime",
        "tamanho_bytes",
        "estado_upload",
        "estado_seguranca",
        "carregado_em",
    )
    list_filter = ("estado_upload", "estado_seguranca")
    readonly_fields = (
        "chave_armazenamento",
        "nome_original",
        "tipo_mime",
        "tamanho_bytes",
        "sha256",
        "estado_upload",
        "estado_seguranca",
        "carregado_por",
        "carregado_em",
        "removido_em",
    )


@admin.register(RequisitoDocumento)
class RequisitoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("tipo_documento", "candidatura", "fase", "estado", "bloqueante")
    list_filter = ("fase", "estado", "obrigatorio", "bloqueante")
    autocomplete_fields = ("candidatura", "beneficiario", "participacao", "tipo_documento")
    readonly_fields = ("estado", "dispensado_em", "dispensado_por", "motivo_dispensa")


@admin.register(Documento)
class DocumentoAdmin(SemEliminacaoAdmin):
    list_display = ("tipo_documento", "candidatura", "fase", "estado_atual")
    list_filter = ("fase", "estado_atual", "tipo_documento")
    search_fields = ("public_id", "titulo")
    readonly_fields = ("public_id", "estado_atual", "criado_por", "criado_em", "atualizado_em")


@admin.register(VersaoDocumento)
class VersaoDocumentoAdmin(SemEliminacaoAdmin):
    list_display = ("documento", "numero", "estado_validacao", "corrente", "carregada_em")
    list_filter = ("estado_validacao", "corrente")
    search_fields = ("documento__public_id", "ficheiro__nome_original")
    readonly_fields = (
        "documento",
        "numero",
        "ficheiro",
        "estado_validacao",
        "corrente",
        "emitido_em",
        "valido_ate",
        "carregada_por",
        "carregada_em",
        "validada_por",
        "validada_em",
        "observacao_validacao",
        "motivo_substituicao",
    )


@admin.register(SnapshotSubmissao)
class SnapshotSubmissaoAdmin(SemEliminacaoAdmin):
    list_display = ("candidatura", "finalidade", "sequencia", "capturado_em")
    list_filter = ("finalidade",)
    readonly_fields = (
        "candidatura",
        "finalidade",
        "sequencia",
        "capturado_em",
        "capturado_por",
        "dados",
        "versao_esquema",
        "hash_conteudo",
        "versoes_documentos",
    )
