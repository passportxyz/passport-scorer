"""Ceramic Cache Models"""

from account.models import EthAddressField
from django.db import models


class CeramicCache(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    stamp = models.JSONField(default=dict)
    created_at = models.DateTimeField(
        auto_now_add=True,
        blank=True,
        null=True,
        help_text="This is the timestamp that this DB record was created (it is not necessarily the stamp issuance timestamp)",
    )

    # Not auto_now because it does not work correctly with bulk updates
    updated_at = models.DateTimeField(
        blank=False,
        null=False,
        help_text="This is the timestamp that this DB record was updated (it is not necessarily the stamp issuance timestamp)",
    )

    class Meta:
        unique_together = ["address", "provider"]


class StampExports(models.Model):
    last_export_ts = models.DateTimeField(auto_now_add=True)
    stamp_total = models.IntegerField(default=0)


class CeramicCacheLegacy(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    stamp = models.JSONField(default=dict)

    class Meta:
        unique_together = ["address", "provider"]
