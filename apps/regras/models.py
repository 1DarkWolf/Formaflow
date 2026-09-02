from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q

from apps.core.models import ModeloTemporal


class ConjuntoRegras(ModeloTemporal):
    class Estado(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ATIVO = "ATIVO", "Ativo"
        SUBSTITUIDO = "SUBSTITUIDO", "Substituído"
        ARQUIVADO = "ARQUIVADO", "Arquivado"

    codigo = models.CharField("código", max_length=50)
    versao = models.PositiveIntegerField("versão")
    designacao = models.CharField("designação", max_length=255)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.RASCUNHO)
    vigente_desde = models.DateField()
    vigente_ate = models.DateField(blank=True, null=True)
    referencia_demonstracao = models.BooleanField(
        "referência de demonstração",
        default=True,
    )
    fonte = models.TextField()
    publicado_em = models.DateTimeField(blank=True, null=True, editable=False)
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        editable=False,
        related_name="conjuntos_regras_publicados",
    )

    class Meta:
        verbose_name = "conjunto de regras"
        verbose_name_plural = "conjuntos de regras"
        ordering = ("codigo", "-versao")
        constraints = [
            models.UniqueConstraint(
                fields=("codigo", "versao"),
                name="regras_conjunto_codigo_versao_unicos",
            ),
            models.CheckConstraint(
                condition=Q(versao__gt=0),
                name="regras_conjunto_versao_positiva",
            ),
            models.CheckConstraint(
                condition=Q(vigente_ate__isnull=True)
                | Q(vigente_ate__gte=models.F("vigente_desde")),
                name="regras_conjunto_vigencia_valida",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} v{self.versao}"

    def save(self, *args, **kwargs):
        if self._foi_publicado():
            raise ValidationError("Um conjunto publicado não pode ser alterado.")
        self.codigo = self.codigo.strip().upper()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._foi_publicado():
            raise ValidationError("Um conjunto publicado não pode ser eliminado.")
        return super().delete(*args, **kwargs)

    def _foi_publicado(self):
        return bool(
            self.pk
            and self.__class__.objects.filter(pk=self.pk, publicado_em__isnull=False).exists()
        )

    def clean(self):
        super().clean()
        self.codigo = self.codigo.strip().upper()
        if self.vigente_ate and self.vigente_ate < self.vigente_desde:
            raise ValidationError(
                {"vigente_ate": "A vigência final não pode ser anterior à inicial."}
            )
        if self.estado != self.Estado.RASCUNHO and not self.publicado_em:
            raise ValidationError("Apenas o serviço de publicação pode ativar regras.")


class ParametroRegra(ModeloTemporal):
    class TipoValor(models.TextChoices):
        INTEIRO = "INTEIRO", "Inteiro"
        DECIMAL = "DECIMAL", "Decimal"
        BOOLEANO = "BOOLEANO", "Booleano"
        TEXTO = "TEXTO", "Texto"
        DATA = "DATA", "Data"
        JSON = "JSON", "JSON"

    conjunto_regras = models.ForeignKey(
        ConjuntoRegras,
        on_delete=models.PROTECT,
        related_name="parametros",
    )
    codigo = models.CharField("código", max_length=80)
    designacao = models.CharField("designação", max_length=255)
    tipo_valor = models.CharField(max_length=10, choices=TipoValor.choices)
    valor = models.JSONField(encoder=DjangoJSONEncoder)
    unidade = models.CharField(max_length=40, blank=True)
    observacoes = models.TextField("observações", blank=True)

    class Meta:
        verbose_name = "parâmetro de regra"
        verbose_name_plural = "parâmetros de regras"
        ordering = ("conjunto_regras", "codigo")
        constraints = [
            models.UniqueConstraint(
                fields=("conjunto_regras", "codigo"),
                name="regras_parametro_codigo_unico_no_conjunto",
            ),
        ]

    def __str__(self):
        return f"{self.codigo}: {self.valor}"

    def save(self, *args, **kwargs):
        if self._conjunto_foi_publicado():
            raise ValidationError("Os parâmetros de um conjunto publicado são imutáveis.")
        self.codigo = self.codigo.strip().upper()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._conjunto_foi_publicado():
            raise ValidationError("Os parâmetros de um conjunto publicado são imutáveis.")
        return super().delete(*args, **kwargs)

    def _conjunto_foi_publicado(self):
        return ConjuntoRegras.objects.filter(
            pk=self.conjunto_regras_id,
            publicado_em__isnull=False,
        ).exists()

    def clean(self):
        super().clean()
        self.codigo = self.codigo.strip().upper()
        valid = {
            self.TipoValor.INTEIRO: self._inteiro_valido,
            self.TipoValor.DECIMAL: self._decimal_valido,
            self.TipoValor.BOOLEANO: lambda: isinstance(self.valor, bool),
            self.TipoValor.TEXTO: lambda: isinstance(self.valor, str),
            self.TipoValor.DATA: self._data_valida,
            self.TipoValor.JSON: lambda: isinstance(self.valor, (dict, list)),
        }
        validator = valid.get(self.tipo_valor)
        if validator is None or not validator():
            raise ValidationError({"valor": "O valor não corresponde ao tipo configurado."})

    def _inteiro_valido(self):
        return isinstance(self.valor, int) and not isinstance(self.valor, bool)

    def _decimal_valido(self):
        if isinstance(self.valor, bool):
            return False
        try:
            Decimal(str(self.valor))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return isinstance(self.valor, (int, float, str))

    def _data_valida(self):
        if not isinstance(self.valor, str):
            return False
        try:
            date.fromisoformat(self.valor)
        except ValueError:
            return False
        return True


class Feriado(ModeloTemporal):
    class Ambito(models.TextChoices):
        NACIONAL = "NACIONAL", "Nacional"
        REGIONAL = "REGIONAL", "Regional"
        MUNICIPAL = "MUNICIPAL", "Municipal"

    data = models.DateField()
    designacao = models.CharField("designação", max_length=150)
    ambito = models.CharField("âmbito", max_length=10, choices=Ambito.choices)
    regiao = models.CharField("região", max_length=120, blank=True)
    ativo = models.BooleanField(default=True)
    fonte = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "feriado"
        verbose_name_plural = "feriados"
        ordering = ("data", "ambito", "regiao")
        constraints = [
            models.UniqueConstraint(
                fields=("data", "ambito", "regiao"),
                name="regras_feriado_data_ambito_regiao_unicos",
            ),
            models.CheckConstraint(
                condition=(Q(ambito="NACIONAL", regiao=""))
                | (~Q(ambito="NACIONAL") & ~Q(regiao="")),
                name="regras_feriado_regiao_coerente",
            ),
        ]

    def __str__(self):
        return f"{self.data:%Y-%m-%d} — {self.designacao}"

    def save(self, *args, **kwargs):
        self._normalizar_regiao()
        return super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        self._normalizar_regiao()
        return super().full_clean(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.ambito != self.Ambito.NACIONAL and not self.regiao:
            raise ValidationError({"regiao": "A região é obrigatória neste âmbito."})

    def _normalizar_regiao(self):
        self.regiao = "" if self.ambito == self.Ambito.NACIONAL else self.regiao.strip().upper()


class TipoDocumento(ModeloTemporal):
    class Categoria(models.TextChoices):
        IDENTIDADE = "IDENTIDADE", "Identidade"
        EMPRESA = "EMPRESA", "Empresa"
        EMPREGO = "EMPREGO", "Emprego"
        FORMACAO = "FORMACAO", "Formação"
        FINANCEIRO = "FINANCEIRO", "Financeiro"
        DECISAO = "DECISAO", "Decisão"
        OUTRO = "OUTRO", "Outro"

    class Sensibilidade(models.TextChoices):
        INTERNO = "INTERNO", "Interno"
        PESSOAL = "PESSOAL", "Pessoal"
        PESSOAL_SENSIVEL = "PESSOAL_SENSIVEL", "Pessoal sensível"

    codigo = models.CharField("código", max_length=80, unique=True)
    designacao = models.CharField("designação", max_length=255)
    categoria = models.CharField(max_length=12, choices=Categoria.choices)
    sensibilidade = models.CharField(max_length=18, choices=Sensibilidade.choices)
    tem_validade = models.BooleanField(default=False)
    apenas_pdf = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        verbose_name = "tipo de documento"
        verbose_name_plural = "tipos de documentos"
        ordering = ("categoria", "designacao")

    def __str__(self):
        return self.designacao

    def save(self, *args, **kwargs):
        self.codigo = self.codigo.strip().upper()
        return super().save(*args, **kwargs)
