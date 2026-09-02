from django.db import transaction

from .models import ContaPagamento


@transaction.atomic
def criar_conta_pagamento(
    *,
    iban,
    nome_titular,
    candidato=None,
    empresa=None,
    principal=False,
):
    conta = ContaPagamento(
        candidato=candidato,
        empresa=empresa,
        nome_titular=nome_titular,
        principal=principal,
    )
    conta.definir_iban(iban)
    conta.full_clean()
    conta.save()
    return conta
