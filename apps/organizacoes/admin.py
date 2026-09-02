from django.contrib import admin

from .forms import ContaPagamentoAdminForm
from .models import (
    AssociacaoEmpresa,
    CertificacaoFormadora,
    ContaPagamento,
    Empresa,
    EntidadeFormadora,
    VinculoLaboral,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("denominacao_legal", "nome_comercial", "localidade", "ativa")
    list_filter = ("ativa", "localidade")
    search_fields = ("denominacao_legal", "nome_comercial", "nipc")
    readonly_fields = ("public_id", "criado_em", "atualizado_em")


@admin.register(AssociacaoEmpresa)
class AssociacaoEmpresaAdmin(admin.ModelAdmin):
    list_display = ("utilizador", "empresa", "papel", "ativa", "inicio_em", "fim_em")
    list_filter = ("papel", "ativa")
    search_fields = ("utilizador__email", "empresa__denominacao_legal")
    autocomplete_fields = ("utilizador", "empresa", "concedida_por")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(VinculoLaboral)
class VinculoLaboralAdmin(admin.ModelAdmin):
    list_display = ("candidato", "situacao", "empresa", "inicio_em", "fim_em")
    list_filter = ("situacao",)
    search_fields = ("candidato__utilizador__email", "empresa__denominacao_legal")
    autocomplete_fields = ("candidato", "empresa", "confirmado_por")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(ContaPagamento)
class ContaPagamentoAdmin(admin.ModelAdmin):
    form = ContaPagamentoAdminForm
    list_display = ("nome_titular", "iban_mascarado", "principal", "ativa")
    list_filter = ("principal", "ativa")
    search_fields = ("nome_titular", "iban_ultimos_4")
    autocomplete_fields = ("candidato", "empresa", "validada_por")
    readonly_fields = (
        "iban_mascarado",
        "validada_em",
        "criado_em",
        "atualizado_em",
    )


@admin.register(EntidadeFormadora)
class EntidadeFormadoraAdmin(admin.ModelAdmin):
    list_display = ("denominacao_legal", "nome_comercial", "ativa")
    list_filter = ("ativa",)
    search_fields = ("denominacao_legal", "nome_comercial", "nipc")
    readonly_fields = ("public_id", "criado_em", "atualizado_em")


@admin.register(CertificacaoFormadora)
class CertificacaoFormadoraAdmin(admin.ModelAdmin):
    list_display = (
        "entidade_formadora",
        "enquadramento",
        "area_codigo",
        "valida_desde",
        "valida_ate",
    )
    list_filter = ("enquadramento",)
    search_fields = (
        "entidade_formadora__denominacao_legal",
        "area_codigo",
        "numero_certificacao",
    )
    autocomplete_fields = ("entidade_formadora", "verificada_por")
    readonly_fields = ("criado_em", "atualizado_em")
