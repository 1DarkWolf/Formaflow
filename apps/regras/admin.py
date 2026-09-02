from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError

from .models import ConjuntoRegras, Feriado, ParametroRegra, TipoDocumento
from .services import publicar_conjunto


class ParametroRegraInline(admin.TabularInline):
    model = ParametroRegra
    extra = 0

    def has_add_permission(self, request, obj):
        return bool(obj is None or obj.publicado_em is None)

    def has_change_permission(self, request, obj=None):
        return bool(obj is None or obj.publicado_em is None)

    def has_delete_permission(self, request, obj=None):
        return bool(obj is None or obj.publicado_em is None)


@admin.register(ConjuntoRegras)
class ConjuntoRegrasAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "versao",
        "designacao",
        "estado",
        "vigente_desde",
        "vigente_ate",
        "referencia_demonstracao",
    )
    list_filter = ("estado", "referencia_demonstracao", "codigo")
    search_fields = ("codigo", "designacao", "fonte")
    readonly_fields = ("publicado_em", "publicado_por", "criado_em", "atualizado_em")
    inlines = (ParametroRegraInline,)
    actions = ("publicar_selecionados",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.publicado_em:
            return tuple(field.name for field in obj._meta.fields if field.name != "id")
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.publicado_em:
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        for conjunto in queryset:
            conjunto.delete()

    @admin.action(description="Publicar conjuntos selecionados")
    def publicar_selecionados(self, request, queryset):
        published = 0
        for conjunto in queryset:
            try:
                publicar_conjunto(conjunto.pk, request.user)
            except PermissionDenied as error:
                self.message_user(request, str(error), level=messages.ERROR)
            except ValidationError as error:
                self.message_user(request, " ".join(error.messages), level=messages.ERROR)
            else:
                published += 1
        if published:
            self.message_user(request, f"Foram publicados {published} conjuntos.")


@admin.register(ParametroRegra)
class ParametroRegraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "designacao", "conjunto_regras", "tipo_valor", "valor")
    list_filter = ("tipo_valor", "conjunto_regras__codigo")
    search_fields = ("codigo", "designacao")
    autocomplete_fields = ("conjunto_regras",)
    readonly_fields = ("criado_em", "atualizado_em")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.conjunto_regras.publicado_em:
            return tuple(field.name for field in obj._meta.fields if field.name != "id")
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.conjunto_regras.publicado_em:
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        for parametro in queryset.select_related("conjunto_regras"):
            parametro.delete()


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ("data", "designacao", "ambito", "regiao", "ativo")
    list_filter = ("ambito", "ativo")
    search_fields = ("designacao", "regiao", "fonte")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "designacao", "categoria", "sensibilidade", "ativo")
    list_filter = ("categoria", "sensibilidade", "ativo", "apenas_pdf")
    search_fields = ("codigo", "designacao")
    readonly_fields = ("criado_em", "atualizado_em")
