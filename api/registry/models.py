from account.models import Community
from django.db import models


class Passport(models.Model):
    address = models.CharField(null=True, blank=False, max_length=100)
    # TODO: shall we drop the did in favour of the address? The DID is specific to a certain network
    # did = models.CharField(null=False, blank=False, max_length=100)
    passport = models.JSONField(default=dict)
    version = models.BigIntegerField(
        help_text="""A counter for passport submissions. This records in which passport
        submission the passport was updated. This will include also submissions when
        stamps have been removed from this passport as part of de-duping""",
        db_index=True,
        null=True,
        blank=True,
    )
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
