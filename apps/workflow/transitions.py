from dataclasses import dataclass

from apps.candidaturas.models import Candidatura


@dataclass(frozen=True)
class DefinicaoTransicao:
    codigo: str
    designacao: str
    origens: tuple[str | None, ...]
    destino: str
    permissao: str
    especializada: bool = False
    exige_motivo: bool = False
    exige_confirmacao: bool = False


TRANSICOES = {
    item.codigo: item
    for item in (
        DefinicaoTransicao(
            "TR-001",
            "Criar candidatura",
            (None,),
            Candidatura.Estado.RASCUNHO,
            "criacao",
            especializada=True,
        ),
        DefinicaoTransicao(
            "TR-002",
            "Validar candidatura",
            (Candidatura.Estado.RASCUNHO,),
            Candidatura.Estado.PRONTA_SUBMISSAO,
            "preparacao",
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-003",
            "Reabrir edição",
            (Candidatura.Estado.PRONTA_SUBMISSAO,),
            Candidatura.Estado.RASCUNHO,
            "preparacao",
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-004",
            "Registar submissão externa",
            (Candidatura.Estado.PRONTA_SUBMISSAO,),
            Candidatura.Estado.SUBMETIDA,
            "submissao",
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-005",
            "Abandonar preparação",
            (Candidatura.Estado.RASCUNHO, Candidatura.Estado.PRONTA_SUBMISSAO),
            Candidatura.Estado.RASCUNHO_ARQUIVADO,
            "preparacao",
            exige_motivo=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-006",
            "Registar início da análise",
            (Candidatura.Estado.SUBMETIDA,),
            Candidatura.Estado.EM_ANALISE,
            "oficial",
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-007",
            "Registar pedido de elementos",
            (Candidatura.Estado.EM_ANALISE,),
            Candidatura.Estado.AGUARDA_ELEMENTOS,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-008",
            "Registar resposta completa",
            (Candidatura.Estado.AGUARDA_ELEMENTOS,),
            Candidatura.Estado.EM_ANALISE,
            "resposta",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-009",
            "Registar decisão favorável",
            (Candidatura.Estado.EM_ANALISE,),
            Candidatura.Estado.APROVADA_AGUARDA_TERMO,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-010",
            "Registar decisão desfavorável",
            (Candidatura.Estado.EM_ANALISE,),
            Candidatura.Estado.INDEFERIDA,
            "oficial",
            especializada=True,
            exige_motivo=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-011",
            "Registar arquivamento oficial",
            (Candidatura.Estado.EM_ANALISE,),
            Candidatura.Estado.ARQUIVADA,
            "oficial",
            especializada=True,
            exige_motivo=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-012",
            "Confirmar desistência externa",
            (
                Candidatura.Estado.SUBMETIDA,
                Candidatura.Estado.EM_ANALISE,
                Candidatura.Estado.AGUARDA_ELEMENTOS,
            ),
            Candidatura.Estado.DESISTIDA,
            "oficial",
            exige_motivo=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-013",
            "Confirmar termo de aceitação",
            (Candidatura.Estado.APROVADA_AGUARDA_TERMO,),
            Candidatura.Estado.APROVADA_ACOMPANHAMENTO,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-014",
            "Registar extinção",
            (Candidatura.Estado.APROVADA_AGUARDA_TERMO,),
            Candidatura.Estado.EXTINTA,
            "oficial",
            exige_motivo=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-015",
            "Iniciar preparação do encerramento",
            (Candidatura.Estado.APROVADA_ACOMPANHAMENTO,),
            Candidatura.Estado.ENCERRAMENTO_PREPARACAO,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-016",
            "Registar submissão do encerramento",
            (Candidatura.Estado.ENCERRAMENTO_PREPARACAO,),
            Candidatura.Estado.ENCERRAMENTO_SUBMETIDO,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-017",
            "Registar início da análise do encerramento",
            (Candidatura.Estado.ENCERRAMENTO_SUBMETIDO,),
            Candidatura.Estado.ENCERRAMENTO_ANALISE,
            "oficial",
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-018",
            "Registar pedido de elementos do encerramento",
            (Candidatura.Estado.ENCERRAMENTO_ANALISE,),
            Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-019",
            "Registar resposta completa do encerramento",
            (Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS,),
            Candidatura.Estado.ENCERRAMENTO_ANALISE,
            "resposta",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-020",
            "Registar conclusão do encerramento",
            (Candidatura.Estado.ENCERRAMENTO_ANALISE,),
            Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-021",
            "Confirmar regularização financeira",
            (Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO,),
            Candidatura.Estado.ENCERRADA,
            "oficial",
            especializada=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-022",
            "Registar revogação",
            (
                Candidatura.Estado.APROVADA_AGUARDA_TERMO,
                Candidatura.Estado.APROVADA_ACOMPANHAMENTO,
                Candidatura.Estado.ENCERRAMENTO_PREPARACAO,
                Candidatura.Estado.ENCERRAMENTO_SUBMETIDO,
                Candidatura.Estado.ENCERRAMENTO_ANALISE,
                Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS,
                Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO,
            ),
            Candidatura.Estado.REVOGADA,
            "oficial",
            exige_motivo=True,
            exige_confirmacao=True,
        ),
        DefinicaoTransicao(
            "TR-023",
            "Corrigir último estado terminal",
            (
                Candidatura.Estado.ENCERRADA,
                Candidatura.Estado.INDEFERIDA,
                Candidatura.Estado.ARQUIVADA,
                Candidatura.Estado.DESISTIDA,
                Candidatura.Estado.EXTINTA,
                Candidatura.Estado.REVOGADA,
                Candidatura.Estado.RASCUNHO_ARQUIVADO,
            ),
            Candidatura.Estado.RASCUNHO,
            "administracao",
            especializada=True,
            exige_motivo=True,
            exige_confirmacao=True,
        ),
    )
}


def obter_transicao(codigo):
    return TRANSICOES.get(str(codigo).strip().upper())
