from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import FormularioAlteracaoUtilizador, FormularioCriacaoUtilizador
from .models import PerfilCandidato, TentativaAutenticacao, Utilizador


@admin.register(Utilizador)
class UtilizadorAdmin(UserAdmin):
    add_form = FormularioCriacaoUtilizador
    form = FormularioAlteracaoUtilizador
    model = Utilizador

    list_display = (
        "email",
        "nome_proprio",
        "apelido",
        "is_active",
        "equipa_interna",
        "is_staff",
    )
    list_filter = ("is_active", "equipa_interna", "is_staff", "is_superuser", "groups")
    ordering = ("email",)
    search_fields = ("email", "nome_proprio", "apelido")
    readonly_fields = ("last_login", "criado_em", "atualizado_em")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identificação", {"fields": ("nome_proprio", "apelido")}),
        (
            "Estado",
            {"fields": ("is_active", "equipa_interna", "is_staff", "is_superuser")},
        ),
        ("Permissões", {"fields": ("groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "criado_em", "atualizado_em")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nome_proprio",
                    "apelido",
                    "password1",
                    "password2",
                    "is_active",
                    "equipa_interna",
                    "is_staff",
                ),
            },
        ),
    )


@admin.register(PerfilCandidato)
class PerfilCandidatoAdmin(admin.ModelAdmin):
    list_display = ("utilizador", "nif", "data_nascimento", "localidade", "pais")
    search_fields = (
        "utilizador__email",
        "utilizador__nome_proprio",
        "utilizador__apelido",
        "nif",
    )
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(TentativaAutenticacao)
class TentativaAutenticacaoAdmin(admin.ModelAdmin):
    list_display = ("chave_abreviada", "falhas", "bloqueado_ate", "atualizado_em")
    readonly_fields = ("chave", "falhas", "janela_iniciada_em", "bloqueado_ate", "atualizado_em")

    def chave_abreviada(self, obj):
        return f"{obj.chave[:12]}…"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
