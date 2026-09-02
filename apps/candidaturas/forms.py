from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.contas.models import PerfilCandidato
from apps.formacoes.models import ComponenteFormacao
from apps.organizacoes.models import ContaPagamento, Empresa, EntidadeFormadora, VinculoLaboral
from apps.organizacoes.selectors import empresas_geridas_por, utilizador_e_administrador
from apps.regras.models import ConjuntoRegras

from .models import BeneficiarioCandidatura, Candidatura


def _conjuntos_vigentes():
    today = timezone.localdate()
    return (
        ConjuntoRegras.objects.filter(
            estado=ConjuntoRegras.Estado.ATIVO,
            publicado_em__isnull=False,
            vigente_desde__lte=today,
        )
        .filter(Q(vigente_ate__isnull=True) | Q(vigente_ate__gte=today))
        .order_by("codigo", "-versao")
    )


class NovaCandidaturaForm(forms.Form):
    tipo = forms.ChoiceField(
        choices=Candidatura.Tipo.choices,
        widget=forms.RadioSelect,
    )
    vinculo = forms.ModelChoiceField(
        label="Candidato e situação de referência",
        queryset=VinculoLaboral.objects.none(),
        required=False,
        help_text="Obrigatório numa candidatura individual.",
    )
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.none(),
        required=False,
        help_text="Obrigatória numa candidatura empresarial.",
    )
    conjunto_regras = forms.ModelChoiceField(
        label="Versão de regras",
        queryset=ConjuntoRegras.objects.none(),
    )

    def __init__(self, *args, utilizador, **kwargs):
        super().__init__(*args, **kwargs)
        companies = empresas_geridas_por(utilizador).filter(ativa=True)
        self.fields["empresa"].queryset = companies
        today = timezone.localdate()
        links = VinculoLaboral.objects.filter(inicio_em__lte=today).filter(
            Q(fim_em__isnull=True) | Q(fim_em__gte=today)
        )
        if not utilizador_e_administrador(utilizador):
            try:
                profile = utilizador.perfil_candidato
            except PerfilCandidato.DoesNotExist:
                profile = None
            personal = Q(candidato=profile) if profile else Q(pk__in=[])
            links = links.filter(personal | Q(empresa__in=companies))
        self.fields["vinculo"].queryset = links.select_related(
            "candidato__utilizador",
            "empresa",
        ).order_by("candidato__utilizador__nome_proprio", "-inicio_em")
        self.fields["conjunto_regras"].queryset = _conjuntos_vigentes()

    def clean(self):
        cleaned = super().clean()
        application_type = cleaned.get("tipo")
        if application_type == Candidatura.Tipo.INDIVIDUAL and not cleaned.get("vinculo"):
            self.add_error("vinculo", "Selecione a situação profissional de referência.")
        if application_type == Candidatura.Tipo.EMPRESARIAL and not cleaned.get("empresa"):
            self.add_error("empresa", "Selecione a empresa titular.")
        return cleaned


class AdicionarBeneficiarioForm(forms.Form):
    candidato = forms.ModelChoiceField(queryset=PerfilCandidato.objects.none())
    versao = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        candidate_ids = (
            VinculoLaboral.objects.filter(
                empresa=candidatura.titular_empresa,
                inicio_em__lte=today,
            )
            .filter(Q(fim_em__isnull=True) | Q(fim_em__gte=today))
            .values("candidato_id")
        )
        self.fields["candidato"].queryset = (
            PerfilCandidato.objects.filter(id__in=candidate_ids, utilizador__is_active=True)
            .exclude(participacoes_candidatura__candidatura=candidatura)
            .select_related("utilizador")
            .distinct()
        )
        self.fields["versao"].initial = candidatura.versao


class AdicionarFormacaoForm(forms.Form):
    beneficiario = forms.ModelChoiceField(queryset=BeneficiarioCandidatura.objects.none())
    entidade_formadora = forms.ModelChoiceField(
        queryset=EntidadeFormadora.objects.filter(ativa=True),
    )
    designacao = forms.CharField(label="Designação da ação", max_length=255)
    area_codigo = forms.CharField(label="Código da área", max_length=20, required=False)
    area_designacao = forms.CharField(
        label="Designação da área",
        max_length=255,
        required=False,
    )
    modalidade = forms.ChoiceField(
        choices=(
            ("Presencial", "Presencial"),
            ("A distância", "A distância"),
            ("Mista", "Mista"),
        )
    )
    inicio_previsto = forms.DateField(
        label="Início previsto",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fim_previsto = forms.DateField(
        label="Fim previsto",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    local = forms.CharField(max_length=255, required=False)
    componente_tipo = forms.ChoiceField(
        label="Tipo da primeira componente",
        choices=ComponenteFormacao.Tipo.choices,
    )
    componente_codigo_cnq = forms.CharField(
        label="Código CNQ",
        max_length=30,
        required=False,
    )
    componente_designacao = forms.CharField(
        label="Designação da componente",
        max_length=255,
    )
    componente_referencial = forms.CharField(
        label="Referencial",
        max_length=255,
        required=False,
    )
    componente_horas = forms.DecimalField(
        label="Horas",
        max_digits=8,
        decimal_places=2,
        min_value=0.01,
    )
    justificacao_extra_cnq = forms.CharField(
        label="Justificação extra-CNQ",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    custo_declarado = forms.DecimalField(
        label="Custo declarado (€)",
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )
    versao = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["beneficiario"].queryset = candidatura.beneficiarios.select_related(
            "candidato__utilizador"
        )
        self.fields["versao"].initial = candidatura.versao

    def clean(self):
        cleaned = super().clean()
        component_type = cleaned.get("componente_tipo")
        code = (cleaned.get("componente_codigo_cnq") or "").strip()
        justification = (cleaned.get("justificacao_extra_cnq") or "").strip()
        if component_type == ComponenteFormacao.Tipo.CNQ and not code:
            self.add_error("componente_codigo_cnq", "O código é obrigatório numa componente CNQ.")
        if component_type == ComponenteFormacao.Tipo.EXTRA_CNQ:
            if code:
                self.add_error(
                    "componente_codigo_cnq",
                    "Uma componente extra-CNQ não pode ter código CNQ.",
                )
            if not justification:
                self.add_error(
                    "justificacao_extra_cnq",
                    "Justifique a relevância desta componente.",
                )
        return cleaned

    def dados_acao(self):
        return {
            "entidade_formadora": self.cleaned_data["entidade_formadora"],
            "designacao": self.cleaned_data["designacao"],
            "area_codigo": self.cleaned_data["area_codigo"],
            "area_designacao": self.cleaned_data["area_designacao"],
            "modalidade": self.cleaned_data["modalidade"],
            "inicio_previsto": self.cleaned_data["inicio_previsto"],
            "fim_previsto": self.cleaned_data["fim_previsto"],
            "local": self.cleaned_data["local"],
        }

    def dados_componente(self):
        return {
            "tipo": self.cleaned_data["componente_tipo"],
            "codigo_cnq": self.cleaned_data["componente_codigo_cnq"],
            "designacao": self.cleaned_data["componente_designacao"],
            "area_codigo": self.cleaned_data["area_codigo"],
            "referencial": self.cleaned_data["componente_referencial"],
            "horas": self.cleaned_data["componente_horas"],
            "justificacao_extra_cnq": self.cleaned_data["justificacao_extra_cnq"],
        }


class DefinirContaPagamentoForm(forms.Form):
    conta_pagamento = forms.ModelChoiceField(
        label="Conta de pagamento",
        queryset=ContaPagamento.objects.none(),
    )
    versao = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, candidatura, **kwargs):
        super().__init__(*args, **kwargs)
        if candidatura.tipo == Candidatura.Tipo.INDIVIDUAL:
            accounts = ContaPagamento.objects.filter(candidato=candidatura.titular_candidato)
        else:
            accounts = ContaPagamento.objects.filter(empresa=candidatura.titular_empresa)
        self.fields["conta_pagamento"].queryset = accounts.filter(ativa=True)
        self.fields["versao"].initial = candidatura.versao
