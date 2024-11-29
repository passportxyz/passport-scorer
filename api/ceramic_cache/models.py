"""Ceramic Cache Models"""

from enum import IntEnum
from typing import Literal

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


type BanType = Literal["account"] | Literal["hash"] | Literal["single_stamp"]


class BanList(models.Model):
    name = models.CharField(
        default="", max_length=256, db_index=True, null=True, blank=True
    )
    description = models.TextField(default="", null=True, blank=True)
    csv_file = models.FileField(max_length=1024, null=False, blank=False)

    def __str__(self):
        return f"#{self.id} {self.name if self.name else ' - no name - '}"


class Ban(models.Model):
    BAN_TYPE_CHOICES = [
        ("account", "Account"),
        ("hash", "Hash"),
        ("single_stamp", "SingleStamps"),
    ]

    type = models.CharField(
        max_length=20, choices=BAN_TYPE_CHOICES, null=False, blank=False, default=None
    )
    provider = models.CharField(default="", max_length=256, db_index=True, blank=True)
    hash = models.CharField(default="", max_length=100, db_index=True, blank=True)
    address = EthAddressField(default="", db_index=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True, db_index=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_run_revoke_matching = models.DateTimeField(
        null=True, blank=True, help_text="Last time revoke_matching_credentials was run"
    )
    ban_list = models.ForeignKey(
        BanList,
        help_text="If set, this ban was created as part of a larger ban list",
        on_delete=models.PROTECT,
        default=None,
        blank=True,
        null=True,
    )

    @classmethod
    def get_bans(cls, *, address: str, hashes: list[str]) -> list["Ban"]:
        """
        Fetch all bans that could affect the given address and/or hashes in one query.

        Returns:
            List of relevant Ban objects
        """
        now = timezone.now()

        return list(
            cls.objects.filter(
                Q(end_time__isnull=True) | Q(end_time__gt=now),
                Q(hash__in=hashes) | Q(address__iexact=address),
            ).select_related()
        )

    @staticmethod
    def check_bans_for(
        bans: list["Ban"], address: str, stamp_hash: str, provider: str
    ) -> tuple[bool, BanType | None, "Ban | None"]:
        """
        Check if a specific credential is banned based on a pre-fetched list of bans.

        Args:
            bans: List of Ban objects from get_bans()
            address: The address to check
            hash: The credential hash to check
            provider: The provider of the credential

        Returns:
            Tuple of (is_banned, ban_type, ban_object)
        """
        parsed_address = address.lower()

        for ban in bans:
            parsed_ban_address = ban.address.lower()

            # Check account-wide ban first
            if (
                ban.type == "account"
                and parsed_ban_address == parsed_address
                and not ban.provider
            ):
                return True, "account", ban

            # Check hash ban
            if ban.type == "hash" and ban.hash == stamp_hash:
                return True, "hash", ban

            # Check address + provider ban
            if (
                ban.type == "single_stamp"
                and parsed_ban_address == parsed_address
                and ban.provider == provider
            ):
                return True, "single_stamp", ban

        return False, None, None

    def clean(self):
        super().clean()

        if self.type not in ("account", "hash", "single_stamp"):
            raise ValidationError(
                f"Invalid value in ban.type: '{self.type}'. See `Wielding the Ban Hammer`."
            )

        if self.type == "account" and not (
            # Account ban (ETH address)
            self.address and not self.hash and not self.provider
        ):
            raise ValidationError(
                "Invalid ban for type 'account'. See `Wielding the Ban Hammer`."
            )

        if self.type == "hash" and not (
            # Account ban (ETH address)
            self.hash and not self.address and not self.provider
        ):
            raise ValidationError(
                "Invalid ban for type 'hash'. See `Wielding the Ban Hammer`."
            )

        if self.type == "single_stamp" and not (
            # Account ban (ETH address)
            self.address and self.provider and not self.hash
        ):
            raise ValidationError(
                "Invalid ban for type 'single_stamp'. See `Wielding the Ban Hammer`."
            )

    def save(self, *args, **kwargs):
        # For details on model validation see https://docs.djangoproject.com/en/5.1/ref/models/instances/#validating-objects
        self.full_clean()
        super().save(*args, **kwargs)

    def revoke_matching_credentials(self):
        """
        Revoke all matching credentials.
        """
        filters = [
            f
            for f in [
                Q(provider=self.provider) if self.provider else None,
                Q(address=self.address) if self.address else None,
                Q(stamp__credentialSubject__hash=self.hash) if self.hash else None,
                Q(deleted_at__isnull=True, revocation__isnull=True),
            ]
            if f is not None
        ]

        stamps = CeramicCache.objects.filter(*filters)

        for stamp in stamps:
            Revocation.objects.create(
                proof_value=stamp.proof_value, ceramic_cache=stamp
            )

        self.last_run_revoke_matching = timezone.now()
        self.save()
