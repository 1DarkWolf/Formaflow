from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.contas.models import PerfilCandidato
from apps.formacoes.models import AcaoFormacao, ComponenteFormacao
from apps.organizacoes.models import VinculoLaboral
from apps.organizacoes.selectors import (
    utilizador_e_administrador,
    utilizador_pode_gerir_empresa,
)
from apps.regras.models import ConjuntoRegras, ParametroRegra

from .exceptions import ConflitoVersao
from .models import (
    AtribuicaoCandidatura,
    BeneficiarioCandidatura,
    Candidatura,
    ParticipacaoFormacao,
    VerificacaoElegibilidade,
)
from .selectors import utilizador_pode_editar_candidatura

CODIGO_LIMITE_BENEFICIARIOS = "CFG-EMPRESA-BENEFICIARIOS"


def _validar_conjunto_para_nova_candidatura(conjunto, data_referencia=None):
    reference_date = data_referencia or timezone.localdate()
    conjunto.refresh_from_db()
    if conjunto.estado != ConjuntoRegras.Estado.ATIVO or not conjunto.publicado_em:
        raise ValidationError("Selecione um conjunto de regras publicado e ativo.")
    if conjunto.vigente_desde > reference_date or (
        conjunto.vigente_ate and conjunto.vigente_ate < reference_date
    ):
        raise ValidationError("O conjunto de regras não está vigente nesta data.")


def _vinculo_vigente(vinculo, data_referencia=None):
    reference_date = data_referencia or timezone.localdate()
    return bool(
        vinculo
        and vinculo.inicio_em <= reference_date
        and (vinculo.fim_em is None or vinculo.fim_em >= reference_date)
    )


def _dados_referencia(vinculo):
    return {
        "situacao_referencia": vinculo.situacao,
        "vinculo_referencia": vinculo,
        "nivel_qualificacao_referencia": vinculo.nivel_qualificacao,
        "inscricao_iefp_referencia": vinculo.inscricao_iefp_em,
    }


def _validar_autor_individual(utilizador, candidato, vinculo):
    if not utilizador or not utilizador.is_authenticated or not utilizador.is_active:
        raise PermissionDenied("A conta não pode criar candidaturas.")
    if not candidato.utilizador.is_active:
        raise ValidationError("O candidato selecionado não tem uma conta ativa.")
    if utilizador_e_administrador(utilizador):
        return
    try:
        if utilizador.perfil_candidato.pk == candidato.pk:
            return
    except PerfilCandidato.DoesNotExist:
        pass
    if vinculo.empresa_id and utilizador_pode_gerir_empresa(utilizador, vinculo.empresa):
        return
    raise PermissionDenied("Não pode criar uma candidatura para este candidato.")


@transaction.atomic
def criar_candidatura_individual(*, criada_por, vinculo_referencia, conjunto_regras):
    if not _vinculo_vigente(vinculo_referencia):
        raise ValidationError("Selecione um vínculo laboral vigente.")
    candidato = vinculo_referencia.candidato
    _validar_autor_individual(criada_por, candidato, vinculo_referencia)
    _validar_conjunto_para_nova_candidatura(conjunto_regras)

    candidatura = Candidatura(
        tipo=Candidatura.Tipo.INDIVIDUAL,
        titular_candidato=candidato,
        conjunto_regras=conjunto_regras,
        criada_por=criada_por,
    )
    candidatura.full_clean()
    candidatura.save()
    beneficiario = BeneficiarioCandidatura(
        candidatura=candidatura,
        candidato=candidato,
        e_titular=True,
        **_dados_referencia(vinculo_referencia),
    )
    beneficiario.full_clean()
    beneficiario.save()
    return candidatura


@transaction.atomic
def criar_candidatura_empresarial(*, criada_por, titular_empresa, conjunto_regras):
    if not utilizador_pode_gerir_empresa(criada_por, titular_empresa):
        raise PermissionDenied("Não pode criar candidaturas para esta empresa.")
    if not titular_empresa.ativa:
        raise ValidationError("Não pode criar uma candidatura para uma empresa inativa.")
    _validar_conjunto_para_nova_candidatura(conjunto_regras)

    candidatura = Candidatura(
        tipo=Candidatura.Tipo.EMPRESARIAL,
        titular_empresa=titular_empresa,
        conjunto_regras=conjunto_regras,
        criada_por=criada_por,
    )
    candidatura.full_clean()
    candidatura.save()
    AtribuicaoCandidatura.objects.create(
        candidatura=candidatura,
        utilizador=criada_por,
        papel=AtribuicaoCandidatura.Papel.RESPONSAVEL,
        principal=True,
        inicio_em=timezone.now(),
        atribuida_por=criada_por,
    )
    return candidatura


def _limite_beneficiarios(candidatura):
    try:
        parameter = candidatura.conjunto_regras.parametros.get(codigo=CODIGO_LIMITE_BENEFICIARIOS)
    except ParametroRegra.DoesNotExist as error:
        raise ValidationError("O limite empresarial não está configurado nesta versão.") from error
    if (
        parameter.tipo_valor != ParametroRegra.TipoValor.INTEIRO
        or isinstance(parameter.valor, bool)
        or not isinstance(parameter.valor, int)
        or parameter.valor < 1
    ):
        raise ValidationError("O limite empresarial configurado é inválido.")
    return parameter.valor


def _bloquear_rascunho(candidatura_id, utilizador, versao_esperada):
    candidatura = (
        Candidatura.objects.select_for_update()
        .select_related(
            "titular_candidato",
            "titular_empresa",
            "conjunto_regras",
            "conta_pagamento",
        )
        .get(pk=candidatura_id)
    )
    if not utilizador_pode_editar_candidatura(utilizador, candidatura):
        raise PermissionDenied("Não pode alterar esta candidatura.")
    if candidatura.versao != versao_esperada:
        raise ConflitoVersao(
            "A candidatura foi alterada noutra sessão. Atualize a página e tente novamente."
        )
    return candidatura


def _incrementar_versao(candidatura):
    Candidatura.objects.filter(pk=candidatura.pk, versao=candidatura.versao).update(
        versao=F("versao") + 1,
        atualizado_em=timezone.now(),
    )
    candidatura.refresh_from_db()


@transaction.atomic
def adicionar_beneficiario(
    *,
    candidatura_id,
    candidato,
    utilizador,
    versao_esperada,
    data_referencia=None,
):
    candidatura = _bloquear_rascunho(candidatura_id, utilizador, versao_esperada)
    if candidatura.tipo != Candidatura.Tipo.EMPRESARIAL:
        raise ValidationError("Só candidaturas empresariais aceitam outros beneficiários.")
    if not candidato.utilizador.is_active:
        raise ValidationError("O candidato selecionado não tem uma conta ativa.")
    if candidatura.beneficiarios.count() >= _limite_beneficiarios(candidatura):
        raise ValidationError("Foi atingido o limite de beneficiários desta versão de regras.")

    reference_date = data_referencia or timezone.localdate()
    vinculo = (
        VinculoLaboral.objects.filter(
            candidato=candidato,
            empresa=candidatura.titular_empresa,
            inicio_em__lte=reference_date,
        )
        .filter(Q(fim_em__isnull=True) | Q(fim_em__gte=reference_date))
        .order_by("-inicio_em")
        .first()
    )
    if not vinculo:
        raise ValidationError("O candidato não possui vínculo vigente com a empresa titular.")
    if candidatura.beneficiarios.filter(candidato=candidato).exists():
        raise ValidationError("Este candidato já pertence à candidatura.")

    beneficiario = BeneficiarioCandidatura(
        candidatura=candidatura,
        candidato=candidato,
        e_titular=False,
        **_dados_referencia(vinculo),
    )
    beneficiario.full_clean()
    beneficiario.save()
    _incrementar_versao(candidatura)
    return beneficiario


@transaction.atomic
def associar_participacao(
    *,
    candidatura_id,
    beneficiario,
    acao_formacao,
    horas_previstas,
    custo_declarado,
    utilizador,
    versao_esperada,
):
    candidatura = _bloquear_rascunho(candidatura_id, utilizador, versao_esperada)
    if beneficiario.candidatura_id != candidatura.pk:
        raise ValidationError("O beneficiário não pertence à candidatura.")
    participacao = ParticipacaoFormacao(
        beneficiario=beneficiario,
        acao_formacao=acao_formacao,
        horas_previstas=horas_previstas,
        custo_declarado=custo_declarado,
    )
    participacao.full_clean()
    participacao.save()
    _incrementar_versao(candidatura)
    return participacao


@transaction.atomic
def criar_formacao_para_beneficiario(
    *,
    candidatura_id,
    beneficiario,
    dados_acao,
    dados_componente,
    custo_declarado,
    utilizador,
    versao_esperada,
):
    candidatura = _bloquear_rascunho(candidatura_id, utilizador, versao_esperada)
    if beneficiario.candidatura_id != candidatura.pk:
        raise ValidationError("O beneficiário não pertence à candidatura.")

    acao = AcaoFormacao(**dados_acao)
    acao.full_clean()
    acao.save()
    componente = ComponenteFormacao(acao_formacao=acao, ordem=1, **dados_componente)
    componente.full_clean()
    componente.save()
    participacao = ParticipacaoFormacao(
        beneficiario=beneficiario,
        acao_formacao=acao,
        horas_previstas=acao.horas_totais,
        custo_declarado=custo_declarado,
    )
    participacao.full_clean()
    participacao.save()
    _incrementar_versao(candidatura)
    return participacao


@transaction.atomic
def definir_conta_pagamento(
    *,
    candidatura_id,
    conta_pagamento,
    utilizador,
    versao_esperada,
):
    candidatura = _bloquear_rascunho(candidatura_id, utilizador, versao_esperada)
    if not conta_pagamento.ativa:
        raise ValidationError("Selecione uma conta de pagamento ativa.")
    candidatura.conta_pagamento = conta_pagamento
    candidatura.full_clean()
    candidatura.save(update_fields=("conta_pagamento", "atualizado_em"))
    _incrementar_versao(candidatura)
    return candidatura


def _guardar_verificacao(
    candidatura,
    codigo,
    resultado,
    observacoes,
    *,
    beneficiario=None,
    participacao=None,
    valor_avaliado=None,
):
    verification, _ = VerificacaoElegibilidade.objects.update_or_create(
        candidatura=candidatura,
        beneficiario=beneficiario,
        participacao=participacao,
        codigo_regra=codigo,
        defaults={
            "tipo_avaliacao": VerificacaoElegibilidade.TipoAvaliacao.AUTOMATICA,
            "resultado": resultado,
            "valor_avaliado": valor_avaliado,
            "observacoes": observacoes,
            "verificada_em": timezone.now(),
            "verificada_por": None,
        },
    )
    return verification


@transaction.atomic
def executar_verificacoes_basicas(*, candidatura_id, utilizador):
    candidatura = _bloquear_rascunho(
        candidatura_id,
        utilizador,
        Candidatura.objects.only("versao").get(pk=candidatura_id).versao,
    )
    beneficiarios = list(candidatura.beneficiarios.prefetch_related("participacoes_formacao"))
    sem_formacao = [item.pk for item in beneficiarios if not item.participacoes_formacao.exists()]
    global_result = (
        VerificacaoElegibilidade.Resultado.CONFORME
        if beneficiarios and not sem_formacao
        else VerificacaoElegibilidade.Resultado.NAO_CONFORME
    )
    _guardar_verificacao(
        candidatura,
        "RN-CAN-005",
        global_result,
        "Todos os beneficiários têm formação associada."
        if global_result == VerificacaoElegibilidade.Resultado.CONFORME
        else "Adicione pelo menos um beneficiário e uma formação por beneficiário.",
        valor_avaliado={
            "beneficiarios": len(beneficiarios),
            "beneficiarios_sem_formacao": len(sem_formacao),
        },
    )
    for beneficiario in beneficiarios:
        link_result = (
            VerificacaoElegibilidade.Resultado.CONFORME
            if beneficiario.vinculo_referencia_id
            else VerificacaoElegibilidade.Resultado.PENDENTE
        )
        _guardar_verificacao(
            candidatura,
            "RN-CAN-004",
            link_result,
            "Vínculo de referência registado."
            if link_result == VerificacaoElegibilidade.Resultado.CONFORME
            else "O vínculo profissional exige confirmação.",
            beneficiario=beneficiario,
        )
        for participacao in beneficiario.participacoes_formacao.select_related("acao_formacao"):
            action = participacao.acao_formacao
            training_result = (
                VerificacaoElegibilidade.Resultado.CONFORME
                if action.tipologia and action.componentes.exists()
                else VerificacaoElegibilidade.Resultado.NAO_CONFORME
            )
            _guardar_verificacao(
                candidatura,
                "RN-FOR-002",
                training_result,
                "A tipologia foi derivada das componentes."
                if training_result == VerificacaoElegibilidade.Resultado.CONFORME
                else "A ação precisa de componentes válidas.",
                beneficiario=beneficiario,
                participacao=participacao,
                valor_avaliado={"tipologia": action.tipologia},
            )
    return candidatura.verificacoes_elegibilidade.all()
