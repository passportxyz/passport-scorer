import json
import os.path
from datetime import datetime
from enum import Enum

from django.core import serializers
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from account.models import Community, EthAddressField
from scorer.settings import (
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_MODEL_SCORE_REQUESTS_TRIGGER_FOLDER,
    BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER,
)


class Passport(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    community = models.ForeignKey(
        Community, related_name="passports", on_delete=models.CASCADE, null=True
    )
    requires_calculation = models.BooleanField(
        null=True,
        help_text="This flag indicates that this passport requires calculation of the score. The score calculation task shall skip calculation unless this flag is set.",
    )

    class Meta:
        unique_together = ["address", "community"]

    def __str__(self):
        return f"Passport #{self.id}, address={self.address}, community_id={self.community_id}"


class Stamp(models.Model):
    passport = models.ForeignKey(
        Passport,
        related_name="stamps",
        on_delete=models.CASCADE,
        null=True,
        db_index=True,
    )
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    credential = models.JSONField(default=dict)

    def __str__(self):
        return (
            f"Stamp #{self.id}, provider={self.provider}, passport={self.passport_id}"
        )


class Score(models.Model):
    class Meta:
        permissions = [("rescore_individual_score", "Can rescore individual scores")]

    class Status:
        PROCESSING = "PROCESSING"
        BULK_PROCESSING = "BULK_PROCESSING"
        DONE = "DONE"
        ERROR = "ERROR"

    STATUS_CHOICES = [
        (Status.PROCESSING, Status.PROCESSING),
        (Status.BULK_PROCESSING, Status.BULK_PROCESSING),
        (Status.DONE, Status.DONE),
        (Status.ERROR, Status.ERROR),
    ]

    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="score", unique=True
    )
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
    last_score_timestamp = models.DateTimeField(
        default=None, null=True, blank=True, db_index=True
    )
    status = models.CharField(
        choices=STATUS_CHOICES, max_length=20, null=True, default=None, db_index=True
    )
    error = models.TextField(null=True, blank=True)
    evidence = models.JSONField(null=True, blank=True)
    stamp_scores = models.JSONField(null=True, blank=True)
    stamps = models.JSONField(null=True, blank=True)

    expiration_date = models.DateTimeField(
        default=None, null=True, blank=True, db_index=True
    )

    def __str__(self):
        return f"Score #{self.id}, score={self.score}, last_score_timestamp={self.last_score_timestamp}, status={self.status}, error={self.error}, evidence={self.evidence}, passport_id={self.passport_id}"

    def clear_on_error(self, error_message: str):
        """
        Clears all fields that should be reset when an error occurs during scoring.
        Update this method if new fields are added that should be cleared on error.
        """
        self.score = None
        self.status = Score.Status.ERROR
        self.last_score_timestamp = None
        self.expiration_date = None
        self.evidence = None
        self.error = error_message
        self.stamp_scores = None
        self.stamps = None


def serialize_score(score: Score):
    json_score = {}
    try:
        serialized_score = serializers.serialize("json", [score])
        json_score = json.loads(serialized_score)[0]
    except:
        json_score["error"] = "Error serializing score"

    return json_score


@receiver(pre_save, sender=Score)
def score_updated(sender, instance, **kwargs):
    if instance.status != Score.Status.DONE:
        return instance

    json_score = serialize_score(instance)

    Event.objects.create(
        action=Event.Action.SCORE_UPDATE,
        address=instance.passport.address,
        community=instance.passport.community,
        data=json_score,
    )

    return instance


class Event(models.Model):
    # Example usage:
    #   obj.action = Event.Action.FIFO_DEDUPLICATION
    class Action(models.TextChoices):
        FIFO_DEDUPLICATION = "FDP"
        LIFO_DEDUPLICATION = "LDP"
        TRUSTALAB_SCORE = "TLS"
        SCORE_UPDATE = "SCU"

    action = models.CharField(
        max_length=3,
        choices=Action.choices,
        blank=False,
    )

    address = EthAddressField(
        blank=True,
        max_length=42,
    )

    ########################################################################################
    # BEGIN: section containing fields that are only used for certain actions
    # and will be set to None otherwise
    ########################################################################################
    community = models.ForeignKey(
        Community,
        on_delete=models.PROTECT,
        related_name="event",
        null=True,
        default=None,
        help_text="""
This field is only used for the SCORE_UPDATE and Deduplication events.
The reason to have this field (and not use the `data` JSON field) is to be able to easily have an index for the community_id for faster lookups.
""",
    )
    ########################################################################################
    # END: section with action - specific fields
    ########################################################################################

    created_at = models.DateTimeField(auto_now_add=True)

    data = models.JSONField()

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "action",
                    "address",
                    "community",
                    "created_at",
                ],
                name="score_history_index",
            ),
        ]


class HashScorerLink(models.Model):
    hash = models.CharField(null=False, blank=False, max_length=100, db_index=True)
    community = models.ForeignKey(
        Community,
        related_name="burned_hashes",
        on_delete=models.CASCADE,
        null=False,
        db_index=True,
    )
    address = EthAddressField(null=False, blank=False, db_index=True)
    expires_at = models.DateTimeField(null=False, blank=False, db_index=True)

    class Meta:
        unique_together = ["hash", "community"]


# For the legacy GTC staking events
class GTCStakeEvent(models.Model):
    event_type = models.CharField(max_length=15)
    round_id = models.IntegerField(db_index=True)
    staker = EthAddressField(blank=False, db_index=True)
    address = EthAddressField(null=True, blank=False, db_index=True)
    amount = models.DecimalField(max_digits=78, decimal_places=18)
    staked = models.BooleanField()
    block_number = models.IntegerField()
    tx_hash = models.CharField(max_length=66)

    class Meta:
        indexes = [
            models.Index(
                fields=["round_id", "address", "staker"],
                name="gtc_staking_index",
            ),
            models.Index(
                fields=["round_id", "staker"],
                name="gtc_staking_index_by_staker",
            ),
        ]


class BatchRequestStatus(str, Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    ERROR = "ERROR"

    def __str__(self):
        return f"{self.value}"


def input_addresses_file_upload_to(_instance, filename):
    # Generate a new filename with the current timestamp prefix
    date_str = datetime.now().isoformat("_", "seconds").replace(":", "-")
    new_filename = f"{date_str}_{filename}"
    return os.path.join(BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER, new_filename)


def results_file_upload_to(_instance, filename):
    # Generate a new filename with the current timestamp prefix
    date_str = datetime.now().isoformat("_", "seconds").replace(":", "-")
    new_filename = f"{date_str}_{filename}"
    return os.path.join(BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER, new_filename)


def trigger_processing_file_upload_to(_instance, filename):
    # Generate a new filename with the current timestamp prefix
    date_str = datetime.now().isoformat("_", "seconds").replace(":", "-")
    new_filename = f"{date_str}_{filename}"
    return os.path.join(BULK_MODEL_SCORE_REQUESTS_TRIGGER_FOLDER, new_filename)


class BatchModelScoringRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    s3_filename = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        help_text="This is deprecated, in favour of `input_addresses_file`",
        db_index=True,
    )
    input_addresses_file = models.FileField(
        max_length=100,
        null=True,
        blank=True,
        upload_to=input_addresses_file_upload_to,
    )
    results_file = models.FileField(
        max_length=100,
        null=True,
        blank=True,
        upload_to=results_file_upload_to,
        help_text="Will contain the exported data",
    )
    model_list = models.CharField(max_length=100, null=False, blank=False)
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status) for status in BatchRequestStatus],
        default=BatchRequestStatus.PENDING,
        db_index=True,
    )
    progress = models.IntegerField(default=0, help_text="Progress in percentage: 0-100")
    last_progress_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last progress update",
    )
    trigger_processing_file = models.FileField(
        max_length=100,
        null=True,
        blank=True,
        upload_to=trigger_processing_file_upload_to,
        help_text="Just a file that is created automatically to trigger the processing. An EventBridge rule will be watching for files created in this folder.",
    )

    def __str__(self):
        return f"{self.id}"


class BatchRequestItemStatus(str, Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    ERROR = "ERROR"

    def __str__(self):
        return f"{self.value}"


class BatchModelScoringRequestItem(models.Model):
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status) for status in BatchRequestItemStatus],
        default=BatchRequestItemStatus.PENDING,
        db_index=True,
    )
    batch_scoring_request = models.ForeignKey(
        BatchModelScoringRequest, on_delete=models.PROTECT, related_name="items"
    )
    address = EthAddressField(null=False, blank=False, db_index=True)
    result = models.JSONField(default=None, null=True, blank=True)

    class Meta:
        unique_together = ["batch_scoring_request", "address"]


class HumanPointsCommunityQualifiedUsers(models.Model):
    """Tracks which communities an address has achieved passing scores in"""

    address = models.CharField(max_length=100, db_index=True)
    community = models.ForeignKey(
        Community, related_name="human_points_qualified_users", on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = "Human Points Community Qualified User"
        verbose_name_plural = "Human Points Community Qualified Users"
        unique_together = ["address", "community"]
        indexes = [
            models.Index(fields=["address"]),
        ]

    def __str__(self):
        return f"HumanPointsCommunityQualifiedUsers - {self.address} qualified in {self.community.name}"


class HumanPoints(models.Model):
    """Records individual human points actions by addresses (normalized without point values)"""

    # Example usage:
    #   obj.action = HumanPoints.Action.PASSPORT_MINT
    class Action(models.TextChoices):
        SCORING_BONUS = "SCB"
        HUMAN_KEYS = "HKY"
        IDENTITY_STAKING_BRONZE = "ISB"
        IDENTITY_STAKING_SILVER = "ISS"
        IDENTITY_STAKING_GOLD = "ISG"
        COMMUNITY_STAKING_BEGINNER = "CSB"
        COMMUNITY_STAKING_EXPERIENCED = "CSE"
        COMMUNITY_STAKING_TRUSTED = "CST"
        PASSPORT_MINT = "PMT"
        HUMAN_ID_MINT = "HIM"

    address = models.CharField(max_length=100, db_index=True)
    action = models.CharField(max_length=3, choices=Action.choices, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    tx_hash = models.CharField(max_length=100, null=True, blank=True)
    chain_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Chain ID for mint actions (PMT, HIM)",
    )

    class Meta:
        verbose_name = "Human Point"
        verbose_name_plural = "Human Points"
        indexes = [
            models.Index(fields=["address", "action"]),
            models.Index(fields=["chain_id", "action"]),
        ]

    def __str__(self):
        return f"HumanPoints - {self.address}: {self.action}"


class HumanPointsMultiplier(models.Model):
    """Stores multipliers for addresses in the Human Points Program"""

    address = models.CharField(max_length=100, primary_key=True)
    multiplier = models.IntegerField(default=2)

    class Meta:
        verbose_name = "Human Points Multiplier"
        verbose_name_plural = "Human Points Multipliers"

    def __str__(self):
        return f"HumanPointsMultiplier - {self.address}: {self.multiplier}x"


class HumanPointsConfig(models.Model):
    """Configuration for point values per action type"""

    action = models.CharField(max_length=50, unique=True, db_index=True)
    points = models.IntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Human Points Configuration"
        verbose_name_plural = "Human Points Configurations"
        indexes = [
            models.Index(fields=["action", "active"]),
        ]

    def __str__(self):
        return f"HumanPointsConfig - {self.action}: {self.points} points {'(active)' if self.active else '(inactive)'}"
