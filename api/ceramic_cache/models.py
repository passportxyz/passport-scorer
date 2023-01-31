"""Ceramic Cache Models"""

from account.models import EthAddressField
from django.db import models


class CeramicCache(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    stamp = models.JSONField(default=dict)
    deleted_at = models.DateTimeField(default=None, null=True, blank=True)

    class Meta:
        unique_together = ["address", "provider"]
