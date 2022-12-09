from django.db import models
from account.models import Community
from scorer_weighted.models import Scorer


class Passport(models.Model):
    did = models.CharField(unique=True, null=False, blank=False, max_length=100)
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

    def __str__(self):
        return f"{self.did}"

class Stamp(models.Model):
    passport = models.ForeignKey(
        Passport, related_name="stamps", on_delete=models.CASCADE, null=True
    )
    community = models.ForeignKey(
        Community, related_name="stamps", on_delete=models.CASCADE, null=True
    )
    hash = models.CharField(
        null=False, blank=False, max_length=100, db_index=True
    )
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
    scorer = models.ForeignKey(Scorer, on_delete=models.PROTECT)
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
