from django.db import models


class Passport(models.Model):
    did = models.CharField(unique=True, null=False, blank=False, max_length=100)
    passport = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.did}"


class Stamp(models.Model):
    passport = models.ForeignKey(
        Passport, related_name="stamps", on_delete=models.CASCADE, null=True
    )
    hash = models.CharField(
        unique=True, null=False, blank=False, max_length=100, db_index=True
    )
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    credential = models.JSONField(default=dict)

    def __str__(self):
        return f"#{self.stamp_id}"
