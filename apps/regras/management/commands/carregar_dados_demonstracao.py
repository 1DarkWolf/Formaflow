from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.organizacoes.models import Empresa, EntidadeFormadora
from apps.regras.models import ConjuntoRegras, Feriado, ParametroRegra, TipoDocumento

PARAMETROS = (
    ("CFG-IDADE-MIN", "Idade mínima", ParametroRegra.TipoValor.INTEIRO, 16, "anos"),
    (
        "CFG-DESEMP-INSCRICAO",
        "Inscrição mínima do desempregado",
        ParametroRegra.TipoValor.INTEIRO,
        90,
        "dias_consecutivos",
    ),
    (
        "CFG-DESEMP-NIVEL-MIN",
        "Qualificação mínima do desempregado",
        ParametroRegra.TipoValor.INTEIRO,
        3,
        "nivel",
    ),
    (
        "CFG-DESEMP-NIVEL-MAX",
        "Qualificação máxima do desempregado",
        ParametroRegra.TipoValor.INTEIRO,
        6,
        "nivel",
    ),
    ("CFG-JANELA-APOIO", "Período de acumulação", ParametroRegra.TipoValor.INTEIRO, 2, "anos"),
    (
        "CFG-EMP-HORAS",
        "Horas máximas do ativo empregado",
        ParametroRegra.TipoValor.INTEIRO,
        50,
        "horas",
    ),
    (
        "CFG-EMP-VALOR-HORA",
        "Valor por hora do ativo empregado",
        ParametroRegra.TipoValor.DECIMAL,
        4,
        "euros_hora",
    ),
    (
        "CFG-EMP-MONTANTE",
        "Apoio máximo do ativo empregado",
        ParametroRegra.TipoValor.DECIMAL,
        175,
        "euros",
    ),
    (
        "CFG-EMP-PERCENTAGEM",
        "Percentagem máxima do custo",
        ParametroRegra.TipoValor.DECIMAL,
        90,
        "percentagem",
    ),
    (
        "CFG-DESEMP-HORAS",
        "Horas máximas do desempregado",
        ParametroRegra.TipoValor.INTEIRO,
        150,
        "horas",
    ),
    (
        "CFG-DESEMP-MONTANTE",
        "Apoio máximo do desempregado",
        ParametroRegra.TipoValor.DECIMAL,
        500,
        "euros",
    ),
    (
        "CFG-IAS",
        "Indexante dos Apoios Sociais de referência",
        ParametroRegra.TipoValor.DECIMAL,
        "438.81",
        "euros",
    ),
    (
        "CFG-BOLSA-IAS-PERCENTAGEM",
        "Percentagem do IAS para bolsa de formação",
        ParametroRegra.TipoValor.DECIMAL,
        35,
        "percentagem",
    ),
    (
        "CFG-REFEICAO-DIARIO",
        "Subsídio diário de refeição de referência",
        ParametroRegra.TipoValor.DECIMAL,
        "4.77",
        "euros_dia",
    ),
    (
        "CFG-EMPRESA-BENEFICIARIOS",
        "Trabalhadores por candidatura",
        ParametroRegra.TipoValor.INTEIRO,
        20,
        "trabalhadores",
    ),
    (
        "CFG-FICHEIRO-TAMANHO",
        "Tamanho máximo de documento",
        ParametroRegra.TipoValor.INTEIRO,
        2,
        "MB",
    ),
    (
        "CFG-ANALISE-PRAZO",
        "Decisão da candidatura",
        ParametroRegra.TipoValor.INTEIRO,
        30,
        "dias_uteis",
    ),
    (
        "CFG-ELEMENTOS-PRAZO",
        "Resposta a elementos adicionais",
        ParametroRegra.TipoValor.INTEIRO,
        10,
        "dias_uteis",
    ),
    (
        "CFG-ACEITACAO-PRAZO",
        "Devolução do termo de aceitação",
        ParametroRegra.TipoValor.INTEIRO,
        10,
        "dias_uteis",
    ),
    (
        "CFG-PRIMEIRA-PRESTACAO",
        "Processamento da primeira prestação",
        ParametroRegra.TipoValor.INTEIRO,
        5,
        "dias_uteis",
    ),
    (
        "CFG-REMANESCENTE",
        "Processamento do remanescente",
        ParametroRegra.TipoValor.INTEIRO,
        10,
        "dias_uteis",
    ),
    (
        "CFG-ENCERRAMENTO",
        "Entrega após o fim da formação",
        ParametroRegra.TipoValor.INTEIRO,
        2,
        "meses",
    ),
    (
        "CFG-RESTITUICAO",
        "Restituição após notificação",
        ParametroRegra.TipoValor.INTEIRO,
        60,
        "dias_consecutivos",
    ),
    (
        "CFG-IMPEDIMENTO",
        "Impedimento após não restituição",
        ParametroRegra.TipoValor.INTEIRO,
        2,
        "anos",
    ),
)

TIPOS_DOCUMENTO = (
    (
        "DOCUMENTO_EMPRESA",
        "Documento constitutivo da entidade empregadora",
        TipoDocumento.Categoria.EMPRESA,
        TipoDocumento.Sensibilidade.INTERNO,
    ),
    (
        "IDENTIFICACAO_CIVIL",
        "Documento de identificação",
        TipoDocumento.Categoria.IDENTIDADE,
        TipoDocumento.Sensibilidade.PESSOAL_SENSIVEL,
    ),
    (
        "SITUACAO_LABORAL",
        "Comprovativo da situação laboral",
        TipoDocumento.Categoria.EMPREGO,
        TipoDocumento.Sensibilidade.PESSOAL,
    ),
    (
        "CURRICULO",
        "Curriculum vitae",
        TipoDocumento.Categoria.EMPREGO,
        TipoDocumento.Sensibilidade.PESSOAL,
    ),
    (
        "DECLARACAO_FORMADORA",
        "Declaração da entidade formadora",
        TipoDocumento.Categoria.FORMACAO,
        TipoDocumento.Sensibilidade.PESSOAL,
    ),
    (
        "CERTIFICADO_FORMACAO",
        "Certificado de formação",
        TipoDocumento.Categoria.FORMACAO,
        TipoDocumento.Sensibilidade.PESSOAL,
    ),
    (
        "COMPROVATIVO_PAGAMENTO",
        "Comprovativo de pagamento",
        TipoDocumento.Categoria.FINANCEIRO,
        TipoDocumento.Sensibilidade.PESSOAL_SENSIVEL,
    ),
    (
        "TITULARIDADE_BANCARIA",
        "Comprovativo de titularidade bancária",
        TipoDocumento.Categoria.FINANCEIRO,
        TipoDocumento.Sensibilidade.PESSOAL_SENSIVEL,
    ),
    (
        "TERMO_ACEITACAO",
        "Termo de aceitação",
        TipoDocumento.Categoria.DECISAO,
        TipoDocumento.Sensibilidade.PESSOAL,
    ),
    (
        "COMUNICACAO_IEFP",
        "Comunicação ou notificação do IEFP",
        TipoDocumento.Categoria.DECISAO,
        TipoDocumento.Sensibilidade.PESSOAL,
    ),
)


class Command(BaseCommand):
    help = "Cria dados estritamente fictícios e idempotentes para demonstração."

    @transaction.atomic
    def handle(self, *args, **options):
        Empresa.objects.get_or_create(
            nipc="123456789",
            defaults={
                "denominacao_legal": "Empresa Demonstração, Lda.",
                "nome_comercial": "Empresa Demo",
                "localidade": "Viseu",
            },
        )
        EntidadeFormadora.objects.get_or_create(
            nipc="111111110",
            defaults={
                "denominacao_legal": "Formadora Demonstração, Lda.",
                "nome_comercial": "Formadora Demo",
            },
        )
        conjunto, _ = ConjuntoRegras.objects.get_or_create(
            codigo="CHEQUE_FORMACAO",
            versao=1,
            defaults={
                "designacao": "Referência académica do Cheque-Formação",
                "vigente_desde": date(2015, 1, 1),
                "referencia_demonstracao": True,
                "fonte": (
                    "Documentos históricos fornecidos para a PAP; confirmar antes de uso real."
                ),
            },
        )

        for codigo, designacao, tipo, valor, unidade in PARAMETROS:
            ParametroRegra.objects.get_or_create(
                conjunto_regras=conjunto,
                codigo=codigo,
                defaults={
                    "designacao": designacao,
                    "tipo_valor": tipo,
                    "valor": valor,
                    "unidade": unidade,
                },
            )

        for codigo, designacao, categoria, sensibilidade in TIPOS_DOCUMENTO:
            TipoDocumento.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "designacao": designacao,
                    "categoria": categoria,
                    "sensibilidade": sensibilidade,
                    "apenas_pdf": True,
                },
            )

        for holiday_date, designation in (
            (date(2026, 1, 1), "Ano Novo — demonstração"),
            (date(2026, 12, 25), "Natal — demonstração"),
        ):
            Feriado.objects.get_or_create(
                data=holiday_date,
                ambito=Feriado.Ambito.NACIONAL,
                regiao="",
                defaults={
                    "designacao": designation,
                    "fonte": "Calendário fictício de demonstração",
                },
            )

        self.stdout.write(
            self.style.SUCCESS("Dados de demonstração disponíveis sem criar duplicados.")
        )
