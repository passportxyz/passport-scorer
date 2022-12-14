from account.models import Community, EthAddressField
from django.db import models


class Passport(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100)
    # TODO: shall we drop the did in favour of the address? The DID is specific to a certain network
    # did = models.CharField(null=False, blank=False, max_length=100)
    passport = models.JSONField(default=dict)
    community = models.ForeignKey(
        Community, related_name="passports", on_delete=models.CASCADE, null=True
    )

    class Meta:
        unique_together = ["address", "community"]

    def __str__(self):
        return f"{self.did}"


class Stamp(models.Model):
    passport = models.ForeignKey(
        Passport, related_name="stamps", on_delete=models.CASCADE, null=True
    )
    community = models.ForeignKey(
        Community, related_name="stamps", on_delete=models.CASCADE, null=True
    )
    hash = models.CharField(null=False, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    credential = models.JSONField(default=dict)

    def __str__(self):
        return f"#{self.hash}"

    class Meta:
        unique_together = ["hash", "community"]


class Score(models.Model):
    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="score"
    )
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
