from django.contrib import admin

from .models import (
    AtribuicaoCandidatura,
    BeneficiarioCandidatura,
    Candidatura,
    ParticipacaoFormacao,
    VerificacaoElegibilidade,
)


class BeneficiarioInline(admin.TabularInline):
    model = BeneficiarioCandidatura
    extra = 0


class AtribuicaoInline(admin.TabularInline):
    model = AtribuicaoCandidatura
    fk_name = "candidatura"
    extra = 0


@admin.register(Candidatura)
class CandidaturaAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "tipo",
        "titular",
        "estado_atual",
        "resultado_decisao",
        "versao",
        "criado_em",
    )
    list_filter = ("tipo", "estado_atual", "resultado_decisao")
    search_fields = (
        "public_id",
        "referencia_externa",
        "titular_candidato__utilizador__email",
        "titular_empresa__denominacao_legal",
    )
    autocomplete_fields = (
        "titular_candidato",
        "titular_empresa",
        "conta_pagamento",
        "conjunto_regras",
        "criada_por",
    )
    readonly_fields = (
        "public_id",
        "estado_atual",
        "resultado_decisao",
        "submetida_em",
        "versao",
        "idempotencia_submissao",
        "criado_em",
        "atualizado_em",
    )
    inlines = (BeneficiarioInline, AtribuicaoInline)


@admin.register(AtribuicaoCandidatura)
class AtribuicaoCandidaturaAdmin(admin.ModelAdmin):
    list_display = ("candidatura", "utilizador", "papel", "principal", "ativa")
    list_filter = ("papel", "principal", "ativa")
    search_fields = ("candidatura__public_id", "utilizador__email")
    autocomplete_fields = ("candidatura", "utilizador", "atribuida_por")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(BeneficiarioCandidatura)
class BeneficiarioCandidaturaAdmin(admin.ModelAdmin):
    list_display = ("candidato", "candidatura", "situacao_referencia", "resultado")
    list_filter = ("situacao_referencia", "resultado", "e_titular")
    search_fields = ("candidato__utilizador__email", "candidatura__public_id")
    autocomplete_fields = ("candidatura", "candidato", "vinculo_referencia")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(ParticipacaoFormacao)
class ParticipacaoFormacaoAdmin(admin.ModelAdmin):
    list_display = (
        "beneficiario",
        "acao_formacao",
        "estado",
        "horas_previstas",
        "custo_declarado",
    )
    list_filter = ("estado",)
    search_fields = (
        "beneficiario__candidato__utilizador__email",
        "acao_formacao__designacao",
    )
    autocomplete_fields = ("beneficiario", "acao_formacao")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(VerificacaoElegibilidade)
class VerificacaoElegibilidadeAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_regra",
        "candidatura",
        "beneficiario",
        "tipo_avaliacao",
        "resultado",
        "verificada_em",
    )
    list_filter = ("tipo_avaliacao", "resultado", "codigo_regra")
    search_fields = ("codigo_regra", "candidatura__public_id")
    autocomplete_fields = (
        "candidatura",
        "beneficiario",
        "participacao",
        "verificada_por",
        "evidencia",
    )
    readonly_fields = ("criado_em", "atualizado_em")
