import calendar
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.candidaturas.models import BeneficiarioCandidatura, Candidatura
from apps.candidaturas.selectors import (
    utilizador_pode_consultar_equipa,
    utilizador_pode_operar_candidatura,
)
from apps.organizacoes.models import VinculoLaboral
from apps.organizacoes.selectors import utilizador_e_administrador
from apps.regras.models import ParametroRegra
from apps.workflow.models import Notificacao, Prazo, Tarefa

from .models import ApoioFinanceiro, MovimentoFinanceiro, Restituicao

CENTIMO = Decimal("0.01")
CODIGO_JANELA_APOIO = "CFG-JANELA-APOIO"
CODIGO_EMP_HORAS = "CFG-EMP-HORAS"
CODIGO_EMP_VALOR_HORA = "CFG-EMP-VALOR-HORA"
CODIGO_EMP_MONTANTE = "CFG-EMP-MONTANTE"
CODIGO_EMP_PERCENTAGEM = "CFG-EMP-PERCENTAGEM"
CODIGO_DESEMP_HORAS = "CFG-DESEMP-HORAS"
CODIGO_DESEMP_MONTANTE = "CFG-DESEMP-MONTANTE"
CODIGO_IAS = "CFG-IAS"
CODIGO_BOLSA_PERCENTAGEM = "CFG-BOLSA-IAS-PERCENTAGEM"
CODIGO_REFEICAO_DIARIO = "CFG-REFEICAO-DIARIO"
CODIGO_RESTITUICAO = "CFG-RESTITUICAO"
ESTADOS_TERMINAIS = {
    Candidatura.Estado.ENCERRADA,
    Candidatura.Estado.INDEFERIDA,
    Candidatura.Estado.ARQUIVADA,
    Candidatura.Estado.DESISTIDA,
    Candidatura.Estado.EXTINTA,
    Candidatura.Estado.REVOGADA,
    Candidatura.Estado.RASCUNHO_ARQUIVADO,
}
ESTADOS_COM_DECISAO_FAVORAVEL = {
    Candidatura.Estado.APROVADA_AGUARDA_TERMO,
    Candidatura.Estado.APROVADA_ACOMPANHAMENTO,
    Candidatura.Estado.ENCERRAMENTO_PREPARACAO,
    Candidatura.Estado.ENCERRAMENTO_SUBMETIDO,
    Candidatura.Estado.ENCERRAMENTO_ANALISE,
    Candidatura.Estado.ENCERRAMENTO_AGUARDA_ELEMENTOS,
    Candidatura.Estado.CONCLUIDA_AGUARDA_PAGAMENTO,
}


def _dinheiro(valor):
    return Decimal(str(valor)).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def _decimal_nao_negativo(valor, nome):
    try:
        result = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({nome: "Indique um número válido."}) from error
    if result < 0:
        raise ValidationError({nome: "O valor não pode ser negativo."})
    return result


def _parametro(conjunto, codigo, *, inteiro=False):
    try:
        parameter = conjunto.parametros.get(codigo=codigo)
    except ParametroRegra.DoesNotExist as error:
        raise ValidationError(f"O parâmetro {codigo} não está configurado.") from error
    try:
        value = Decimal(str(parameter.valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError(f"O parâmetro {codigo} é inválido.") from error
    if value < 0 or (inteiro and value != value.to_integral_value()):
        raise ValidationError(f"O parâmetro {codigo} é inválido.")
    return int(value) if inteiro else value


def utilizador_pode_gerir_financeiro(utilizador, candidatura):
    return bool(
        utilizador_pode_operar_candidatura(utilizador, candidatura)
        and (
            utilizador_e_administrador(utilizador)
            or utilizador_pode_consultar_equipa(utilizador, candidatura)
        )
    )


def _exigir_operacao(utilizador, candidatura):
    if not utilizador_pode_operar_candidatura(utilizador, candidatura):
        raise PermissionDenied("Não pode calcular os apoios desta candidatura.")


def _exigir_gestao(utilizador, candidatura):
    if not utilizador_pode_gerir_financeiro(utilizador, candidatura):
        raise PermissionDenied("Não pode registar valores financeiros oficiais.")


def calcular_apoio_formacao_empregado(
    *,
    horas,
    custo,
    financiamento_terceiros=0,
    horas_disponiveis=50,
    montante_disponivel=175,
    valor_hora=4,
    percentagem_maxima=90,
):
    hours = _decimal_nao_negativo(horas, "horas")
    cost = _decimal_nao_negativo(custo, "custo")
    third_party = _decimal_nao_negativo(financiamento_terceiros, "financiamento_terceiros")
    available_hours = _decimal_nao_negativo(horas_disponiveis, "horas_disponiveis")
    available_amount = _decimal_nao_negativo(montante_disponivel, "montante_disponivel")
    hourly = _decimal_nao_negativo(valor_hora, "valor_hora")
    percentage = _decimal_nao_negativo(percentagem_maxima, "percentagem_maxima")
    eligible_hours = min(hours, available_hours)
    net_cost = max(cost - third_party, Decimal("0"))
    by_hours = eligible_hours * hourly
    by_cost = net_cost * percentage / Decimal("100")
    amount = _dinheiro(min(by_hours, by_cost, available_amount))
    return {
        "valor": amount,
        "horas_elegiveis": eligible_hours,
        "custo_liquido": _dinheiro(net_cost),
        "limite_horas": _dinheiro(by_hours),
        "limite_percentagem": _dinheiro(by_cost),
        "limite_montante": _dinheiro(available_amount),
        "horas_excedidas": hours > available_hours,
    }


def calcular_apoio_formacao_desempregado(
    *,
    horas,
    custo,
    financiamento_terceiros=0,
    horas_disponiveis=150,
    montante_disponivel=500,
):
    hours = _decimal_nao_negativo(horas, "horas")
    cost = _decimal_nao_negativo(custo, "custo")
    third_party = _decimal_nao_negativo(financiamento_terceiros, "financiamento_terceiros")
    available_hours = _decimal_nao_negativo(horas_disponiveis, "horas_disponiveis")
    available_amount = _decimal_nao_negativo(montante_disponivel, "montante_disponivel")
    eligible_hours = min(hours, available_hours)
    net_cost = max(cost - third_party, Decimal("0"))
    amount = _dinheiro(min(net_cost, available_amount))
    return {
        "valor": amount,
        "horas_elegiveis": eligible_hours,
        "custo_liquido": _dinheiro(net_cost),
        "limite_montante": _dinheiro(available_amount),
        "horas_excedidas": hours > available_hours,
    }


def calcular_bolsa_formacao(*, horas, ias, percentagem_ias=35):
    hours = _decimal_nao_negativo(horas, "horas")
    ias_value = _decimal_nao_negativo(ias, "ias")
    percentage = _decimal_nao_negativo(percentagem_ias, "percentagem_ias")
    hourly_value = ias_value * percentage / Decimal("100") * Decimal("12")
    hourly_value /= Decimal("52") * Decimal("30")
    return _dinheiro(hours * hourly_value)


def calcular_subsidio_refeicao(*, duracoes_diarias, valor_diario):
    daily_value = _decimal_nao_negativo(valor_diario, "valor_diario")
    eligible_days = sum(
        _decimal_nao_negativo(duration, "duracoes_diarias") >= Decimal("3")
        for duration in duracoes_diarias
    )
    return {"dias_elegiveis": eligible_days, "valor": _dinheiro(eligible_days * daily_value)}


def _somar_anos(data, anos):
    day = min(data.day, calendar.monthrange(data.year + anos, data.month)[1])
    return data.replace(year=data.year + anos, day=day)


def _consumo_janela(beneficiario, candidatura, data_referencia):
    years = _parametro(candidatura.conjunto_regras, CODIGO_JANELA_APOIO, inteiro=True)
    previous = list(
        ApoioFinanceiro.objects.filter(
            beneficiario__candidato=beneficiario.candidato,
            tipo=ApoioFinanceiro.Tipo.FORMACAO,
            confirmado_em__isnull=False,
        )
        .exclude(beneficiario__candidatura=candidatura)
        .select_related("beneficiario__candidatura")
        .order_by("confirmado_em", "pk")
    )
    reference_date = data_referencia.date() if hasattr(data_referencia, "date") else data_referencia
    previous.sort(
        key=lambda support: (
            support.beneficiario.candidatura.submetida_em or support.confirmado_em,
            support.pk,
        )
    )
    window = None
    current_window = None
    for support in previous:
        window_origin = support.beneficiario.candidatura.submetida_em or support.confirmado_em
        start = timezone.localtime(window_origin).date()
        if current_window is None or start >= current_window[1]:
            current_window = (start, _somar_anos(start, years))
        if current_window[0] <= reference_date < current_window[1]:
            window = current_window
            break
    if not window:
        return Decimal("0"), Decimal("0"), None
    consumed_hours = Decimal("0")
    consumed_amount = Decimal("0")
    for support in previous:
        window_origin = support.beneficiario.candidatura.submetida_em or support.confirmado_em
        submission_date = timezone.localtime(window_origin).date()
        if window[0] <= submission_date < window[1]:
            consumed_hours += Decimal(str(support.decomposicao_calculo.get("horas_elegiveis", 0)))
            official = support.valor_final
            if official is None:
                official = support.valor_aprovado or Decimal("0")
            consumed_amount += official
    return consumed_hours, consumed_amount, window


def _mapping_value(mapping, key, default=None):
    if key in mapping:
        return mapping[key]
    return mapping.get(str(key), default)


def _json_calculo(result, **extra):
    data = {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in result.items()
        if key != "valor"
    }
    data.update(extra)
    return data


@transaction.atomic
def calcular_estimativas_candidatura(
    *,
    candidatura_id,
    utilizador,
    usar_valores_finais=False,
    financiamentos_terceiros=None,
    apoios_sociais=None,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("conjunto_regras", "titular_empresa", "titular_candidato")
        .get(pk=candidatura_id)
    )
    _exigir_operacao(utilizador, candidature)
    if candidature.estado_atual in ESTADOS_TERMINAIS:
        raise ValidationError("Uma candidatura em estado terminal não pode ser recalculada.")
    if not candidature.conjunto_regras_id:
        raise ValidationError("A candidatura não tem uma versão de regras associada.")
    third_party_values = financiamentos_terceiros or {}
    social_values = apoios_sociais or {}
    reference = candidature.submetida_em or timezone.now()
    supports = []
    participations = candidature.beneficiarios.select_related("candidato").prefetch_related(
        "participacoes_formacao"
    )
    for beneficiary in participations:
        if beneficiary.resultado not in {
            BeneficiarioCandidatura.Resultado.PENDENTE,
            BeneficiarioCandidatura.Resultado.DEFERIDA,
        }:
            continue
        consumed_hours, consumed_amount, window = _consumo_janela(
            beneficiary, candidature, reference
        )
        employed = beneficiary.situacao_referencia != VinculoLaboral.Situacao.DESEMPREGADO
        max_hours_code = CODIGO_EMP_HORAS if employed else CODIGO_DESEMP_HORAS
        max_amount_code = CODIGO_EMP_MONTANTE if employed else CODIGO_DESEMP_MONTANTE
        max_hours = _parametro(candidature.conjunto_regras, max_hours_code)
        max_amount = _parametro(candidature.conjunto_regras, max_amount_code)
        remaining_hours = max(max_hours - consumed_hours, Decimal("0"))
        remaining_amount = max(max_amount - consumed_amount, Decimal("0"))
        for participation in beneficiary.participacoes_formacao.all():
            if usar_valores_finais:
                if (
                    participation.horas_frequentadas is None
                    or participation.custo_pago_formadora is None
                ):
                    raise ValidationError(
                        "Registe as horas frequentadas e o custo pago antes do cálculo final."
                    )
                hours = participation.horas_frequentadas
                cost = participation.custo_pago_formadora
            else:
                hours = participation.horas_previstas
                cost = participation.custo_declarado
            third_party = _mapping_value(third_party_values, participation.pk, 0)
            common = {
                "horas": hours,
                "custo": cost,
                "financiamento_terceiros": third_party,
                "horas_disponiveis": remaining_hours,
                "montante_disponivel": remaining_amount,
            }
            if employed:
                result = calcular_apoio_formacao_empregado(
                    **common,
                    valor_hora=_parametro(candidature.conjunto_regras, CODIGO_EMP_VALOR_HORA),
                    percentagem_maxima=_parametro(
                        candidature.conjunto_regras, CODIGO_EMP_PERCENTAGEM
                    ),
                )
                formula = "min(horas × valor/hora, 90% custo líquido, saldo monetário)"
            else:
                result = calcular_apoio_formacao_desempregado(**common)
                formula = "min(custo líquido, saldo monetário), dentro do saldo de horas"
            support, _ = ApoioFinanceiro.objects.get_or_create(
                beneficiario=beneficiary,
                participacao=participation,
                tipo=ApoioFinanceiro.Tipo.FORMACAO,
                defaults={"conjunto_regras": candidature.conjunto_regras},
            )
            support.custo_declarado = cost
            support.financiamento_terceiros = _dinheiro(third_party)
            support.valor_elegivel = result["valor"]
            support.valor_estimado = result["valor"]
            support.decomposicao_calculo = _json_calculo(
                result,
                formula=formula,
                valores_finais=usar_valores_finais,
                janela=[item.isoformat() for item in window] if window else None,
                horas_consumidas=str(consumed_hours),
                montante_consumido=str(_dinheiro(consumed_amount)),
                parametros=[max_hours_code, max_amount_code],
            )
            support.calculado_em = timezone.now()
            support.calculado_por = utilizador
            support.conjunto_regras = candidature.conjunto_regras
            if support.valor_aprovado is None:
                support.estado = (
                    ApoioFinanceiro.Estado.ESTIMADO
                    if result["valor"]
                    else ApoioFinanceiro.Estado.SEM_APOIO
                )
            support.full_clean()
            support.save()
            supports.append(support)
            remaining_hours = max(
                remaining_hours - Decimal(str(result["horas_elegiveis"])), Decimal("0")
            )
            remaining_amount = max(remaining_amount - result["valor"], Decimal("0"))
            if not employed:
                supports.extend(
                    _calcular_apoios_sociais(
                        candidature=candidature,
                        beneficiary=beneficiary,
                        participation=participation,
                        hours=hours,
                        options=_mapping_value(social_values, participation.pk, {}) or {},
                        user=utilizador,
                    )
                )
    return supports


def _calcular_apoios_sociais(*, candidature, beneficiary, participation, hours, options, user):
    results = []
    definitions = []
    if options.get("bolsa"):
        ias = _parametro(candidature.conjunto_regras, CODIGO_IAS)
        percentage = _parametro(candidature.conjunto_regras, CODIGO_BOLSA_PERCENTAGEM)
        value = calcular_bolsa_formacao(horas=hours, ias=ias, percentagem_ias=percentage)
        definitions.append(
            (
                ApoioFinanceiro.Tipo.BOLSA,
                value,
                {
                    "formula": "horas × (percentagem IAS) × 12 / (52 × 30)",
                    "horas": str(hours),
                    "ias": str(ias),
                    "percentagem_ias": str(percentage),
                },
            )
        )
    if options.get("refeicao"):
        daily = _parametro(candidature.conjunto_regras, CODIGO_REFEICAO_DIARIO)
        days = participation.dias_tres_ou_mais_horas or 0
        value = _dinheiro(Decimal(days) * daily)
        definitions.append(
            (
                ApoioFinanceiro.Tipo.REFEICAO,
                value,
                {
                    "formula": "dias com pelo menos 3 horas × valor diário",
                    "dias_elegiveis": days,
                    "valor_diario": str(daily),
                },
            )
        )
    if "transporte" in options and options.get("transporte") is not None:
        value = _dinheiro(_decimal_nao_negativo(options["transporte"], "transporte"))
        definitions.append(
            (
                ApoioFinanceiro.Tipo.TRANSPORTE,
                value,
                {"formula": "custo de transporte coletivo comprovado"},
            )
        )
    for support_type, value, decomposition in definitions:
        support, _ = ApoioFinanceiro.objects.get_or_create(
            beneficiario=beneficiary,
            participacao=participation,
            tipo=support_type,
            defaults={"conjunto_regras": candidature.conjunto_regras},
        )
        support.valor_elegivel = value
        support.valor_estimado = value
        support.decomposicao_calculo = decomposition
        support.calculado_em = timezone.now()
        support.calculado_por = user
        support.conjunto_regras = candidature.conjunto_regras
        if support.valor_aprovado is None:
            support.estado = (
                ApoioFinanceiro.Estado.ESTIMADO if value else ApoioFinanceiro.Estado.SEM_APOIO
            )
        support.full_clean()
        support.save()
        results.append(support)
    selected_types = {item[0] for item in definitions}
    stale = ApoioFinanceiro.objects.filter(
        beneficiario=beneficiary,
        participacao=participation,
        tipo__in=(
            ApoioFinanceiro.Tipo.BOLSA,
            ApoioFinanceiro.Tipo.REFEICAO,
            ApoioFinanceiro.Tipo.TRANSPORTE,
        ),
        valor_aprovado__isnull=True,
    ).exclude(tipo__in=selected_types)
    stale.update(
        valor_elegivel=Decimal("0"),
        valor_estimado=Decimal("0"),
        estado=ApoioFinanceiro.Estado.SEM_APOIO,
        decomposicao_calculo={"motivo": "Apoio social não pedido no cálculo atual."},
        calculado_em=timezone.now(),
        calculado_por=user,
        atualizado_em=timezone.now(),
    )
    return results


def total_confirmado_apoio(apoio):
    return sum(
        (
            movement.valor_assinado
            for movement in apoio.movimentos.filter(estado=MovimentoFinanceiro.Estado.CONFIRMADO)
        ),
        Decimal("0"),
    )


def recalcular_estado_apoio(apoio):
    refunds = Restituicao.objects.filter(
        candidatura=apoio.beneficiario.candidatura,
    ).filter(Q(beneficiario__isnull=True) | Q(beneficiario=apoio.beneficiario))
    if refunds.filter(
        estado__in=(Restituicao.Estado.PENDENTE, Restituicao.Estado.PARCIAL)
    ).exists():
        state = ApoioFinanceiro.Estado.RESTITUICAO_PENDENTE
    elif refunds.filter(estado=Restituicao.Estado.PAGA).exists():
        state = ApoioFinanceiro.Estado.RESTITUIDO
    elif refunds.filter(
        estado__in=(Restituicao.Estado.DISPENSADA, Restituicao.Estado.REGULARIZADA)
    ).exists():
        state = ApoioFinanceiro.Estado.REGULARIZADO
    else:
        target = apoio.valor_final
        if target is None:
            target = apoio.valor_aprovado
        if target is None:
            target = apoio.valor_estimado or Decimal("0")
        paid = total_confirmado_apoio(apoio)
        pending_types = set(
            apoio.movimentos.filter(estado=MovimentoFinanceiro.Estado.PREVISTO).values_list(
                "tipo", flat=True
            )
        )
        if target <= 0:
            state = ApoioFinanceiro.Estado.SEM_APOIO
        elif paid >= target:
            state = ApoioFinanceiro.Estado.PAGO
        elif paid > 0:
            state = (
                ApoioFinanceiro.Estado.PAGAMENTO_FINAL_PENDENTE
                if MovimentoFinanceiro.Tipo.REMANESCENTE in pending_types
                else ApoioFinanceiro.Estado.PARCIALMENTE_PAGO
            )
        elif MovimentoFinanceiro.Tipo.PRIMEIRA_PRESTACAO in pending_types:
            state = ApoioFinanceiro.Estado.PRIMEIRA_PRESTACAO_PENDENTE
        elif MovimentoFinanceiro.Tipo.REMANESCENTE in pending_types:
            state = ApoioFinanceiro.Estado.PAGAMENTO_FINAL_PENDENTE
        elif apoio.valor_aprovado is not None:
            state = ApoioFinanceiro.Estado.APROVADO
        else:
            state = ApoioFinanceiro.Estado.ESTIMADO
    ApoioFinanceiro.objects.filter(pk=apoio.pk).update(estado=state, atualizado_em=timezone.now())
    apoio.estado = state
    return state


def _prazo_previsto(apoio, movement_type):
    deadline_type = (
        Prazo.Tipo.PRIMEIRA_PRESTACAO
        if movement_type == MovimentoFinanceiro.Tipo.PRIMEIRA_PRESTACAO
        else Prazo.Tipo.REMANESCENTE
    )
    deadline = (
        apoio.beneficiario.candidatura.prazos.filter(tipo=deadline_type)
        .order_by("-criado_em")
        .first()
    )
    return deadline.limite_efetivo if deadline else None


def gerar_movimentos_previstos(apoio, utilizador):
    target = apoio.valor_final
    if target is None:
        target = apoio.valor_aprovado
    if target is None:
        return []
    if target <= 0:
        apoio.movimentos.filter(estado=MovimentoFinanceiro.Estado.PREVISTO).update(
            estado=MovimentoFinanceiro.Estado.CANCELADO,
            atualizado_em=timezone.now(),
        )
        recalcular_estado_apoio(apoio)
        return []
    confirmed_total = total_confirmado_apoio(apoio)
    first_confirmed = apoio.movimentos.filter(
        tipo=MovimentoFinanceiro.Tipo.PRIMEIRA_PRESTACAO,
        direcao=MovimentoFinanceiro.Direcao.CREDITO,
        estado=MovimentoFinanceiro.Estado.CONFIRMADO,
    ).exists()
    if apoio.tipo == ApoioFinanceiro.Tipo.FORMACAO and not first_confirmed:
        first = _dinheiro(target * Decimal("0.5"))
        remaining = max(target - first - confirmed_total, Decimal("0"))
        planned = [(MovimentoFinanceiro.Tipo.PRIMEIRA_PRESTACAO, first)]
        if remaining:
            planned.append((MovimentoFinanceiro.Tipo.REMANESCENTE, remaining))
    else:
        remaining = max(target - confirmed_total, Decimal("0"))
        planned = [(MovimentoFinanceiro.Tipo.REMANESCENTE, remaining)] if remaining else []
    planned_types = {item[0] for item in planned}
    apoio.movimentos.filter(estado=MovimentoFinanceiro.Estado.PREVISTO).exclude(
        tipo__in=planned_types
    ).update(
        estado=MovimentoFinanceiro.Estado.CANCELADO,
        atualizado_em=timezone.now(),
    )
    generated = []
    for movement_type, value in planned:
        active = apoio.movimentos.filter(
            tipo=movement_type,
            direcao=MovimentoFinanceiro.Direcao.CREDITO,
            estado=MovimentoFinanceiro.Estado.PREVISTO,
        ).first()
        if active and active.valor == value:
            expected_date = _prazo_previsto(apoio, movement_type)
            if active.previsto_para != expected_date:
                MovimentoFinanceiro.objects.filter(pk=active.pk).update(
                    previsto_para=expected_date,
                    atualizado_em=timezone.now(),
                )
                active.previsto_para = expected_date
            generated.append(active)
            continue
        if active:
            MovimentoFinanceiro.objects.filter(pk=active.pk).update(
                estado=MovimentoFinanceiro.Estado.CANCELADO,
                atualizado_em=timezone.now(),
            )
        version = timezone.now().isoformat()
        key = f"previsto:{movement_type}:{version}"[:100]
        movement, _ = MovimentoFinanceiro.objects.get_or_create(
            apoio=apoio,
            chave_idempotencia=key,
            defaults={
                "tipo": movement_type,
                "direcao": MovimentoFinanceiro.Direcao.CREDITO,
                "valor": value,
                "previsto_para": _prazo_previsto(apoio, movement_type),
                "estado": MovimentoFinanceiro.Estado.PREVISTO,
                "registado_por": utilizador,
            },
        )
        generated.append(movement)
    recalcular_estado_apoio(apoio)
    return generated


def sincronizar_movimentos_previstos(candidatura, utilizador):
    movements = []
    for support in ApoioFinanceiro.objects.filter(
        beneficiario__candidatura=candidatura,
        valor_aprovado__isnull=False,
    ):
        movements.extend(gerar_movimentos_previstos(support, utilizador))
    return movements


@transaction.atomic
def confirmar_valores_oficiais(
    *,
    apoio_id,
    utilizador,
    valor_aprovado,
    confirmado_em,
    valor_final=None,
    referencia_externa="",
    evidencia=None,
):
    support = (
        ApoioFinanceiro.objects.select_for_update()
        .select_related("beneficiario__candidatura", "participacao")
        .get(pk=apoio_id)
    )
    _exigir_gestao(utilizador, support.beneficiario.candidatura)
    if support.beneficiario.candidatura.estado_atual not in ESTADOS_COM_DECISAO_FAVORAVEL:
        raise ValidationError("Os valores oficiais exigem uma decisão favorável registada.")
    if support.beneficiario.resultado != BeneficiarioCandidatura.Resultado.DEFERIDA:
        raise ValidationError("O beneficiário não possui um resultado favorável.")
    approved = _dinheiro(_decimal_nao_negativo(valor_aprovado, "valor_aprovado"))
    final = None
    if valor_final is not None:
        final = _dinheiro(_decimal_nao_negativo(valor_final, "valor_final"))
    if not confirmado_em:
        raise ValidationError({"confirmado_em": "Indique a data da confirmação."})
    if timezone.is_naive(confirmado_em):
        confirmado_em = timezone.make_aware(confirmado_em)
    support.valor_aprovado = approved
    support.valor_final = final
    support.confirmado_em = confirmado_em
    support.confirmado_por = utilizador
    support.referencia_externa = referencia_externa.strip()
    support.evidencia = evidencia
    support.estado = ApoioFinanceiro.Estado.APROVADO
    support.full_clean()
    support.save()
    gerar_movimentos_previstos(support, utilizador)
    return support


@transaction.atomic
def registar_movimento(
    *,
    apoio_id,
    utilizador,
    tipo,
    direcao,
    valor,
    estado,
    chave_idempotencia,
    previsto_para=None,
    efetivado_em=None,
    referencia_externa="",
    comprovativo=None,
):
    support = (
        ApoioFinanceiro.objects.select_for_update()
        .select_related("beneficiario__candidatura")
        .get(pk=apoio_id)
    )
    _exigir_gestao(utilizador, support.beneficiario.candidatura)
    if support.valor_aprovado is None:
        raise ValidationError("Confirme primeiro o valor oficial desta linha de apoio.")
    key = str(chave_idempotencia or "").strip()
    if not key or len(key) > 100:
        raise ValidationError({"chave_idempotencia": "Indique uma chave válida."})
    existing = MovimentoFinanceiro.objects.filter(apoio=support, chave_idempotencia=key).first()
    if existing:
        return existing
    if efetivado_em and timezone.is_naive(efetivado_em):
        efetivado_em = timezone.make_aware(efetivado_em)
    movement = MovimentoFinanceiro(
        apoio=support,
        tipo=tipo,
        direcao=direcao,
        valor=_dinheiro(_decimal_nao_negativo(valor, "valor")),
        previsto_para=previsto_para,
        efetivado_em=efetivado_em,
        estado=estado,
        referencia_externa=referencia_externa.strip(),
        comprovativo=comprovativo,
        registado_por=utilizador,
        chave_idempotencia=key,
    )
    movement.full_clean()
    movement.save()
    if estado == MovimentoFinanceiro.Estado.CONFIRMADO:
        MovimentoFinanceiro.objects.filter(
            apoio=support,
            tipo=tipo,
            direcao=direcao,
            estado=MovimentoFinanceiro.Estado.PREVISTO,
        ).exclude(pk=movement.pk).update(
            estado=MovimentoFinanceiro.Estado.CANCELADO,
            atualizado_em=timezone.now(),
        )
    recalcular_estado_apoio(support)
    return movement


@transaction.atomic
def registar_risco_restituicao(*, candidatura_id, utilizador, motivo, chave_idempotencia):
    candidature = Candidatura.objects.select_for_update().get(pk=candidatura_id)
    _exigir_gestao(utilizador, candidature)
    if candidature.estado_atual in {
        Candidatura.Estado.RASCUNHO,
        Candidatura.Estado.PRONTA_SUBMISSAO,
    }:
        raise ValidationError("Ainda não existe um processo externo onde registar este risco.")
    reason = motivo.strip()
    if not reason:
        raise ValidationError({"motivo": "Descreva o risco identificado."})
    key = str(chave_idempotencia or "").strip()
    if not key:
        raise ValidationError({"chave_idempotencia": "Indique uma chave válida."})
    task, _ = Tarefa.objects.get_or_create(
        chave_deduplicacao=f"financeiro:risco:{candidature.pk}:{key}"[:150],
        estado__in=(Tarefa.Estado.ABERTA, Tarefa.Estado.EM_EXECUCAO),
        defaults={
            "candidatura": candidature,
            "atribuida_a": utilizador,
            "tipo": "ANALISAR_RISCO_RESTITUICAO",
            "titulo": "Analisar possível restituição",
            "descricao": reason,
            "prioridade": Tarefa.Prioridade.ALTA,
        },
    )
    Notificacao.objects.get_or_create(
        destinatario=utilizador,
        chave_deduplicacao=f"financeiro:risco:{candidature.pk}:{key}"[:180],
        defaults={
            "candidatura": candidature,
            "tarefa": task,
            "codigo": "RISCO_RESTITUICAO",
            "titulo": task.titulo,
            "mensagem": reason,
            "prioridade": Notificacao.Prioridade.URGENTE,
            "estado": Notificacao.Estado.ENVIADA,
            "enviada_em": timezone.now(),
        },
    )
    return task


@transaction.atomic
def registar_restituicao_oficial(
    *,
    candidatura_id,
    utilizador,
    notificada_em,
    valor,
    motivo,
    chave_idempotencia,
    referencia_externa="",
    evidencia=None,
    beneficiario=None,
):
    candidature = (
        Candidatura.objects.select_for_update()
        .select_related("conjunto_regras")
        .get(pk=candidatura_id)
    )
    _exigir_gestao(utilizador, candidature)
    allowed_refund_states = ESTADOS_COM_DECISAO_FAVORAVEL | {
        Candidatura.Estado.ENCERRADA,
        Candidatura.Estado.REVOGADA,
    }
    if candidature.estado_atual not in allowed_refund_states:
        raise ValidationError("A candidatura ainda não admite uma restituição oficial.")
    key = str(chave_idempotencia or "").strip()
    if not key or len(key) > 100:
        raise ValidationError({"chave_idempotencia": "Indique uma chave válida."})
    existing = Restituicao.objects.filter(candidatura=candidature, chave_idempotencia=key).first()
    if existing:
        return existing
    if beneficiario and beneficiario.candidatura_id != candidature.pk:
        raise ValidationError({"beneficiario": "O beneficiário não pertence à candidatura."})
    if not notificada_em:
        raise ValidationError({"notificada_em": "Indique a data da notificação."})
    if timezone.is_naive(notificada_em):
        notificada_em = timezone.make_aware(notificada_em)
    duration = _parametro(candidature.conjunto_regras, CODIGO_RESTITUICAO, inteiro=True)
    limit = notificada_em + timedelta(days=duration)
    deadline = Prazo(
        candidatura=candidature,
        beneficiario=beneficiario,
        tipo=Prazo.Tipo.RESTITUICAO,
        codigo_regra=CODIGO_RESTITUICAO,
        conjunto_regras=candidature.conjunto_regras,
        inicio_em=notificada_em,
        unidade=Prazo.Unidade.DIAS_CONSECUTIVOS,
        duracao=duration,
        limite_calculado=limit,
    )
    deadline.full_clean()
    deadline.save()
    refund = Restituicao(
        candidatura=candidature,
        beneficiario=beneficiario,
        prazo=deadline,
        notificada_em=notificada_em,
        data_limite=limit,
        valor=_dinheiro(_decimal_nao_negativo(valor, "valor")),
        motivo=motivo.strip(),
        referencia_externa=referencia_externa.strip(),
        evidencia=evidencia,
        registada_por=utilizador,
        chave_idempotencia=key,
    )
    refund.full_clean()
    refund.save()
    task = Tarefa(
        candidatura=candidature,
        beneficiario=beneficiario,
        atribuida_a=utilizador,
        tipo="ACOMPANHAR_RESTITUICAO",
        titulo="Acompanhar restituição comunicada",
        descricao=refund.motivo,
        prioridade=Tarefa.Prioridade.CRITICA,
        data_limite=limit,
        prazo_origem=deadline,
        chave_deduplicacao=f"financeiro:restituicao:{refund.pk}"[:150],
    )
    task.full_clean()
    task.save()
    Notificacao.objects.get_or_create(
        destinatario=utilizador,
        chave_deduplicacao=f"financeiro:restituicao:{refund.pk}:inicial",
        defaults={
            "candidatura": candidature,
            "tarefa": task,
            "prazo": deadline,
            "codigo": "RESTITUICAO_OFICIAL",
            "titulo": task.titulo,
            "mensagem": f"Regularize a restituição até {limit:%d/%m/%Y}.",
            "prioridade": Notificacao.Prioridade.CRITICA,
            "estado": Notificacao.Estado.ENVIADA,
            "enviada_em": timezone.now(),
        },
    )
    for support in ApoioFinanceiro.objects.filter(beneficiario__candidatura=candidature).filter(
        Q(beneficiario=beneficiario) if beneficiario else Q()
    ):
        recalcular_estado_apoio(support)
    return refund


@transaction.atomic
def atualizar_restituicao(
    *,
    restituicao_id,
    utilizador,
    valor_restituido,
    regularizada_em=None,
    dispensada=False,
    referencia_externa="",
    evidencia=None,
):
    refund = (
        Restituicao.objects.select_for_update()
        .select_related("candidatura", "prazo")
        .get(pk=restituicao_id)
    )
    _exigir_gestao(utilizador, refund.candidatura)
    paid = _dinheiro(_decimal_nao_negativo(valor_restituido, "valor_restituido"))
    if paid > refund.valor:
        raise ValidationError({"valor_restituido": "O valor excede o montante notificado."})
    final = dispensada or paid == refund.valor
    if final and not regularizada_em:
        raise ValidationError({"regularizada_em": "Indique a data da regularização."})
    if regularizada_em and timezone.is_naive(regularizada_em):
        regularizada_em = timezone.make_aware(regularizada_em)
    refund.valor_restituido = paid
    refund.regularizada_em = regularizada_em if final else None
    refund.referencia_externa = referencia_externa.strip() or refund.referencia_externa
    refund.evidencia = evidencia or refund.evidencia
    if dispensada:
        refund.estado = Restituicao.Estado.DISPENSADA
    elif paid == refund.valor:
        refund.estado = Restituicao.Estado.PAGA
    elif paid > 0:
        refund.estado = Restituicao.Estado.PARCIAL
    else:
        refund.estado = Restituicao.Estado.PENDENTE
    refund.full_clean()
    refund.save()
    if final:
        Prazo.objects.filter(pk=refund.prazo_id).update(
            estado=Prazo.Estado.CUMPRIDO, atualizado_em=timezone.now()
        )
        Tarefa.objects.filter(
            prazo_origem=refund.prazo,
            estado__in=(Tarefa.Estado.ABERTA, Tarefa.Estado.EM_EXECUCAO),
        ).update(
            estado=Tarefa.Estado.CONCLUIDA,
            concluida_em=regularizada_em,
            concluida_por=utilizador,
            atualizado_em=timezone.now(),
        )
    for support in ApoioFinanceiro.objects.filter(beneficiario__candidatura=refund.candidatura):
        recalcular_estado_apoio(support)
    return refund


def candidatura_pronta_para_conclusao(candidatura):
    deferred = candidatura.beneficiarios.filter(
        resultado=BeneficiarioCandidatura.Resultado.DEFERIDA
    )
    if not deferred.exists():
        return False
    for beneficiary in deferred:
        participations = beneficiary.participacoes_formacao.all()
        if not participations.exists():
            return False
        if participations.exclude(
            apoios_financeiros__tipo=ApoioFinanceiro.Tipo.FORMACAO,
            apoios_financeiros__valor_final__isnull=False,
            apoios_financeiros__confirmado_em__isnull=False,
            apoios_financeiros__confirmado_por__isnull=False,
        ).exists():
            return False
    return True


@transaction.atomic
def validar_encerramento_financeiro(*, candidatura, utilizador, sem_pagamento=False, motivo=""):
    _exigir_gestao(utilizador, candidatura)
    supports = ApoioFinanceiro.objects.filter(beneficiario__candidatura=candidatura)
    if sem_pagamento:
        if not motivo.strip():
            raise ValidationError("A decisão sem pagamento exige uma justificação.")
        if MovimentoFinanceiro.objects.filter(
            apoio__in=supports,
            estado=MovimentoFinanceiro.Estado.CONFIRMADO,
        ).exists():
            raise ValidationError(
                "Já existem movimentos confirmados; registe a regularização efetiva."
            )
        MovimentoFinanceiro.objects.filter(
            apoio__in=supports,
            estado__in=(MovimentoFinanceiro.Estado.PREVISTO, MovimentoFinanceiro.Estado.FALHOU),
        ).update(
            estado=MovimentoFinanceiro.Estado.CANCELADO,
            atualizado_em=timezone.now(),
        )
        supports.update(
            estado=ApoioFinanceiro.Estado.REGULARIZADO,
            atualizado_em=timezone.now(),
        )
        return True
    if not candidatura_pronta_para_conclusao(candidatura):
        raise ValidationError("Faltam valores financeiros finais confirmados.")
    if MovimentoFinanceiro.objects.filter(
        apoio__in=supports,
        estado__in=(MovimentoFinanceiro.Estado.PREVISTO, MovimentoFinanceiro.Estado.FALHOU),
    ).exists():
        raise ValidationError("Existem movimentos financeiros pendentes ou falhados.")
    if Restituicao.objects.filter(
        candidatura=candidatura,
        estado__in=(Restituicao.Estado.PENDENTE, Restituicao.Estado.PARCIAL),
    ).exists():
        raise ValidationError("Existe uma restituição por regularizar.")
    for support in supports:
        recalcular_estado_apoio(support)
        if support.estado not in {
            ApoioFinanceiro.Estado.SEM_APOIO,
            ApoioFinanceiro.Estado.PAGO,
            ApoioFinanceiro.Estado.RESTITUIDO,
            ApoioFinanceiro.Estado.REGULARIZADO,
        }:
            raise ValidationError("Existem apoios financeiros por regularizar.")
    return True
