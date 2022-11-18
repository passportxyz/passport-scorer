from django.db import models

from registry.models import Passport


class ApuScorer(models.Model):
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    accepted_providers = models.JSONField(default=list, blank=True, null=True)


class Score(models.Model):
    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="apu_scores"
    )
    scorer = models.ForeignKey(ApuScorer, on_delete=models.PROTECT)


class Combo(models.Model):
    scorer = models.ForeignKey(ApuScorer, on_delete=models.PROTECT)
    passport = models.ForeignKey(Passport, on_delete=models.PROTECT)
    combo = models.JSONField(default=list, blank=True, null=True, db_index=True)
    count = models.IntegerField(default=0, db_index=True)


class NumInfo(models.Model):
    scorer = models.ForeignKey(ApuScorer, on_delete=models.PROTECT)
    stamp_count = models.IntegerField(default=0, blank=True, null=True, db_index=True)
    count = models.IntegerField(default=0, db_index=True)
