from django.contrib import admin

from .models import ApoioFinanceiro, MovimentoFinanceiro, Restituicao


@admin.register(ApoioFinanceiro)
class ApoioFinanceiroAdmin(admin.ModelAdmin):
    list_display = (
        "beneficiario",
        "tipo",
        "valor_estimado",
        "valor_aprovado",
        "valor_final",
        "estado",
    )
    list_filter = ("tipo", "estado", "moeda")
    search_fields = (
        "beneficiario__candidato__utilizador__email",
        "beneficiario__candidatura__public_id",
        "referencia_externa",
    )
    autocomplete_fields = (
        "beneficiario",
        "participacao",
        "conjunto_regras",
        "calculado_por",
        "confirmado_por",
        "evidencia",
    )
    readonly_fields = ("estado", "criado_em", "atualizado_em")


@admin.register(MovimentoFinanceiro)
class MovimentoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ("apoio", "tipo", "direcao", "valor", "estado", "efetivado_em")
    list_filter = ("tipo", "direcao", "estado")
    search_fields = (
        "apoio__beneficiario__candidatura__public_id",
        "referencia_externa",
        "chave_idempotencia",
    )
    autocomplete_fields = ("apoio", "comprovativo", "registado_por")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(Restituicao)
class RestituicaoAdmin(admin.ModelAdmin):
    list_display = (
        "candidatura",
        "beneficiario",
        "valor",
        "valor_restituido",
        "estado",
        "data_limite",
    )
    list_filter = ("estado",)
    search_fields = (
        "candidatura__public_id",
        "referencia_externa",
        "chave_idempotencia",
    )
    autocomplete_fields = (
        "candidatura",
        "beneficiario",
        "prazo",
        "evidencia",
        "registada_por",
    )
    readonly_fields = ("estado", "criado_em", "atualizado_em")
