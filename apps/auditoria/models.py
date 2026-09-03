from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class RegistoAuditoriaQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Os registos de auditoria são imutáveis.")

    def delete(self):
        raise ValidationError("Os registos de auditoria não podem ser eliminados.")


class RegistoAuditoria(models.Model):
    class Resultado(models.TextChoices):
        SUCESSO = "SUCESSO", "Sucesso"
        RECUSADO = "RECUSADO", "Recusado"
        ERRO = "ERRO", "Erro"

    utilizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registos_auditoria",
        blank=True,
        null=True,
    )
    acao = models.CharField("ação", max_length=100)
    tipo_objeto = models.CharField(max_length=100)
    id_objeto = models.CharField(max_length=100, blank=True)
    public_id_objeto = models.UUIDField(blank=True, null=True)
    ocorrido_em = models.DateTimeField(default=timezone.now, editable=False)
    resultado = models.CharField(max_length=10, choices=Resultado.choices)
    id_pedido = models.CharField(max_length=100, blank=True)
    id_correlacao = models.CharField(max_length=100, blank=True)
    hash_ip = models.CharField(max_length=64, blank=True)
    metadados = models.JSONField(default=dict, blank=True)

    objects = RegistoAuditoriaQuerySet.as_manager()

    class Meta:
        verbose_name = "registo de auditoria"
        verbose_name_plural = "registos de auditoria"
        ordering = ("-ocorrido_em", "-pk")
        indexes = [
            models.Index(fields=("acao", "ocorrido_em"), name="auditoria_acao_data_idx"),
            models.Index(
                fields=("tipo_objeto", "public_id_objeto"),
                name="auditoria_objeto_publico_idx",
            ),
        ]

    def __str__(self):
        return f"{self.acao} — {self.get_resultado_display()}"

    def save(self, *args, **kwargs):
        if self.pk and self.__class__.objects.filter(pk=self.pk).exists():
            raise ValidationError("Os registos de auditoria são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Os registos de auditoria não podem ser eliminados.")
