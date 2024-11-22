"""Ceramic Cache Models"""

from enum import IntEnum

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

from account.models import EthAddressField


class CeramicCache(models.Model):
    class StampType(IntEnum):
        V1 = 1
        V2 = 2

    class ComposeDBSaveStatus(models.TextChoices):
        PENDING = "pending"
        SAVED = "saved"
        FAILED = "failed"

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

    proof_value = models.CharField(
        null=False, blank=False, max_length=256, db_index=True
    )

    # NOTE! auto_now is here to make tests easier, but it is not
    # supported for bulk updates so it should be set explicitly
    updated_at = models.DateTimeField(
        blank=False,
        null=False,
        auto_now=True,
        help_text="This is the timestamp that this DB record was updated (it is not necessarily the stamp issuance timestamp)",
    )

    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="This is the timestamp that this DB record was deleted",
    )

    type = models.IntegerField(
        default=StampType.V1,
        choices=[(tag.value, tag.name) for tag in StampType],
        help_text="TO BE DELETED - this is not used",
    )

    compose_db_save_status = models.CharField(
        max_length=10,
        choices=ComposeDBSaveStatus.choices,
        default="",
        blank=True,
        db_index=True,
    )

    compose_db_stream_id = models.CharField(
        max_length=100,
        default="",
        blank=True,
        help_text="Compose db stream ID for CREDENTIAL WRAPPER",
        db_index=True,
    )

    issuance_date = models.DateTimeField(
        null=True, db_index=True
    )  # stamp['issuanceDate']
    expiration_date = models.DateTimeField(
        null=True, db_index=True
    )  # stamp['expirationDate']

    class Meta:
        unique_together = ["type", "address", "provider", "deleted_at"]

        constraints = [
            # UniqueConstraint for non-deleted records
            UniqueConstraint(
                fields=["type", "address", "provider"],
                name="unique_non_deleted_provider_for_address",
                condition=Q(deleted_at__isnull=True),
            ),
            # UniqueConstraint for deleted records
            UniqueConstraint(
                fields=["type", "address", "provider", "deleted_at"],
                name="unique_deleted_provider_for_address",
                condition=Q(deleted_at__isnull=False),
            ),
        ]


class StampExports(models.Model):
    last_export_ts = models.DateTimeField(auto_now_add=True)
    stamp_total = models.IntegerField(default=0)


class CeramicCacheLegacy(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    stamp = models.JSONField(default=dict, db_index=True)

    class Meta:
        unique_together = ["address", "provider"]


class Revocation(models.Model):
    proof_value = models.CharField(
        null=False, blank=False, max_length=256, db_index=True
    )

    # This is to provide efficient filtering (allows use of JOIN)
    ceramic_cache = models.OneToOneField(
        CeramicCache,
        on_delete=models.CASCADE,
        related_name="revocation",
        null=False,
        blank=False,
        db_index=True,
        unique=True,
    )

    def __str__(self):
        return f"Revocation #{self.pk}, proof_value={self.proof_value}"


class Ban(models.Model):
    provider = models.CharField(default="", max_length=256, db_index=True, blank=True)
    hash = models.CharField(default="", max_length=100, db_index=True, blank=True)
    address = EthAddressField(default="", db_index=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def check_ban(cls, *, provider: str, hash: str, address: str) -> tuple[bool, str]:
        """
        Check if there is an active ban that matches the given credential.
        Returns a tuple of (is_banned, message).
        """
        parsed_address = address.lower()
        now = timezone.now()
        active_ban = cls.objects.filter(
            Q(end_time__isnull=True) | Q(end_time__gt=now),
            Q(hash=hash)  # specific credential ban
            | Q(address=parsed_address, provider="")  # all credentials for address
            | Q(
                address=parsed_address, provider=provider
            ),  # specific provider for address
        ).first()

        if not active_ban:
            return False, ""

        # Build detailed message
        if active_ban.end_time:
            time_remaining = active_ban.end_time - now
            days = time_remaining.days
            message = f"Banned until {active_ban.end_time.strftime('%Y-%m-%d')} ({days} days remaining)"
        else:
            message = "Banned indefinitely"

        if active_ban.reason:
            message += f". Reason: {active_ban.reason}"

        # Add context about what triggered the ban
        if active_ban.hash == hash:
            message += " (credential hash banned)"
        elif active_ban.address == parsed_address and active_ban.provider == provider:
            message += f" (address banned for {provider})"
        elif active_ban.address == parsed_address:
            message += " (address banned)"

        return True, message

    def clean(self):
        super().clean()
        if not any(
            [
                self.hash,  # hash only is valid
                self.address,  # address only is valid
                (self.address and self.provider),  # address + type is valid
            ]
        ):
            raise ValidationError("Invalid ban. See `Wielding the Ban Hammer`.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
