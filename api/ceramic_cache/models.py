from account.models import EthAddressField
from django.db import models

"""Ceramic Cache Models"""


class CeramicCache(models.Model):
    """Ceramic Cache Model"""

    address = EthAddressField(null=True, blank=False, max_length=100)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    passport = models.JSONField(default=dict)

    class Meta:
        unique_together = ["address", "provider"]
