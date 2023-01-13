from account.models import Community, EthAddressField
from django.db import models


class Passport(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100)
    passport = models.JSONField(default=dict, null=True)
    community = models.ForeignKey(
        Community, related_name="passports", on_delete=models.CASCADE, null=True
    )

    class Meta:
        unique_together = ["address", "community"]

    def __str__(self):
        return f"{self.address}"


class Stamp(models.Model):
    passport = models.ForeignKey(
        Passport, related_name="stamps", on_delete=models.CASCADE, null=True
    )
    hash = models.CharField(null=False, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    credential = models.JSONField(default=dict)

    def __str__(self):
        return f"#{self.hash}"

    class Meta:
        unique_together = ["hash", "passport"]


class Score(models.Model):
    class Status:
        PROCESSING = "PROCESSING"
        DONE = "DONE"
        ERROR = "ERROR"

    STATUS_CHOICES = [
        (Status.PROCESSING, Status.PROCESSING),
        (Status.DONE, Status.DONE),
        (Status.ERROR, Status.ERROR),
    ]

    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="score"
    )
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
    last_score_timestamp = models.DateTimeField(default=None, null=True, blank=True)
    status = models.CharField(
        choices=STATUS_CHOICES, max_length=20, null=True, default=None
    )
    error = models.TextField(null=True, blank=True)
    evidence = models.JSONField(null=True, blank=True)
