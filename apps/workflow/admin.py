from django.contrib import admin

from .models import (
    Notificacao,
    PedidoElementos,
    PedidoEncerramento,
    Prazo,
    QuestaoPedido,
    RespostaQuestao,
    SuspensaoPrazo,
    Tarefa,
    TermoAceitacao,
    TransicaoCandidatura,
)


class SemEliminacaoAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TransicaoCandidatura)
class TransicaoCandidaturaAdmin(SemEliminacaoAdmin):
    list_display = (
        "codigo",
        "candidatura",
        "estado_anterior",
        "estado_novo",
        "efetiva_em",
        "ator",
    )
    list_filter = ("codigo", "origem", "estado_novo")
    search_fields = ("candidatura__public_id", "referencia_externa", "chave_idempotencia")
    readonly_fields = (
        "candidatura",
        "beneficiario",
        "codigo",
        "estado_anterior",
        "estado_novo",
        "efetiva_em",
        "registada_em",
        "ator",
        "origem",
        "referencia_externa",
        "motivo",
        "evidencia",
        "conjunto_regras",
        "versao_anterior",
        "versao_nova",
        "corrige_transicao",
        "chave_idempotencia",
    )


@admin.register(PedidoElementos)
class PedidoElementosAdmin(SemEliminacaoAdmin):
    list_display = ("id", "candidatura", "fase", "estado", "recebido_em", "data_limite")
    list_filter = ("fase", "estado")
    search_fields = ("candidatura__public_id", "referencia_externa")
    autocomplete_fields = ("candidatura", "evidencia", "registado_por")


@admin.register(QuestaoPedido)
class QuestaoPedidoAdmin(SemEliminacaoAdmin):
    list_display = ("pedido", "ordem", "destinatario", "obrigatoria")
    list_filter = ("destinatario", "obrigatoria", "exige_documento")
    autocomplete_fields = ("pedido", "beneficiario", "tipo_documento_pedido")
    search_fields = ("texto", "pedido__candidatura__public_id")


@admin.register(RespostaQuestao)
class RespostaQuestaoAdmin(SemEliminacaoAdmin):
    list_display = ("questao", "numero", "estado", "autor", "submetida_em")
    list_filter = ("estado",)
    search_fields = ("questao__texto", "questao__pedido__candidatura__public_id")
    readonly_fields = (
        "questao",
        "numero",
        "texto",
        "estado",
        "autor",
        "criada_em",
        "submetida_em",
        "versoes_documentos",
    )


@admin.register(TermoAceitacao)
class TermoAceitacaoAdmin(admin.ModelAdmin):
    list_display = ("candidatura", "estado", "notificado_em", "data_limite")
    list_filter = ("estado", "fora_prazo")
    autocomplete_fields = ("candidatura", "validado_por", "documento")


@admin.register(PedidoEncerramento)
class PedidoEncerramentoAdmin(admin.ModelAdmin):
    list_display = ("candidatura", "estado", "preparacao_iniciada_em", "submetido_em")
    list_filter = ("estado", "resultado_final")
    autocomplete_fields = ("candidatura", "snapshot_submissao")


@admin.register(Prazo)
class PrazoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "candidatura", "estado", "inicio_em", "limite_efetivo")
    list_filter = ("tipo", "estado", "unidade")
    autocomplete_fields = (
        "candidatura",
        "beneficiario",
        "conjunto_regras",
        "transicao_origem",
        "corrigido_por",
    )
    search_fields = ("candidatura__public_id", "codigo_regra")


@admin.register(SuspensaoPrazo)
class SuspensaoPrazoAdmin(SemEliminacaoAdmin):
    list_display = ("prazo", "inicio_em", "fim_em", "origem")
    list_filter = ("origem",)
    autocomplete_fields = ("prazo", "pedido_elementos", "registada_por")


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "candidatura", "atribuida_a", "estado", "prioridade")
    list_filter = ("estado", "prioridade", "tipo")
    search_fields = ("titulo", "candidatura__public_id", "chave_deduplicacao")
    autocomplete_fields = ("candidatura", "beneficiario", "atribuida_a", "concluida_por")


@admin.register(Notificacao)
class NotificacaoAdmin(SemEliminacaoAdmin):
    list_display = ("titulo", "destinatario", "estado", "prioridade", "criado_em")
    list_filter = ("estado", "prioridade", "codigo")
    search_fields = ("titulo", "destinatario__email", "chave_deduplicacao")
    readonly_fields = ("criado_em", "atualizado_em")
