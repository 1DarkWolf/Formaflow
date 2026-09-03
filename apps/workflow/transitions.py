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
    )
}


def obter_transicao(codigo):
    return TRANSICOES.get(str(codigo).strip().upper())
