from django.contrib import admin

from .models import RegistoAuditoria


@admin.register(RegistoAuditoria)
class RegistoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("ocorrido_em", "acao", "tipo_objeto", "utilizador", "resultado")
    list_filter = ("resultado", "acao", "tipo_objeto")
    search_fields = ("acao", "tipo_objeto", "id_objeto", "public_id_objeto")
    readonly_fields = tuple(field.name for field in RegistoAuditoria._meta.fields)
    date_hierarchy = "ocorrido_em"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False
