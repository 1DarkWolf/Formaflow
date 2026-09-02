from django.contrib import admin

from .models import AcaoFormacao, ComponenteFormacao


class ComponenteFormacaoInline(admin.TabularInline):
    model = ComponenteFormacao
    extra = 0


@admin.register(AcaoFormacao)
class AcaoFormacaoAdmin(admin.ModelAdmin):
    list_display = (
        "designacao",
        "entidade_formadora",
        "tipologia",
        "inicio_previsto",
        "fim_previsto",
        "horas_totais",
        "estado",
    )
    list_filter = ("tipologia", "estado", "modalidade")
    search_fields = (
        "designacao",
        "referencia_externa",
        "entidade_formadora__denominacao_legal",
    )
    autocomplete_fields = ("entidade_formadora",)
    readonly_fields = ("tipologia", "horas_totais", "criado_em", "atualizado_em")
    inlines = (ComponenteFormacaoInline,)


@admin.register(ComponenteFormacao)
class ComponenteFormacaoAdmin(admin.ModelAdmin):
    list_display = ("designacao", "acao_formacao", "ordem", "tipo", "horas")
    list_filter = ("tipo",)
    search_fields = ("designacao", "codigo_cnq", "acao_formacao__designacao")
    autocomplete_fields = ("acao_formacao",)
    readonly_fields = ("criado_em", "atualizado_em")
