from django.db import models


class ModeloTemporal(models.Model):
    """Common timestamps for mutable domain records."""

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
