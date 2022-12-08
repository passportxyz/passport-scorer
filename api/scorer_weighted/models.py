from django.db import models

from registry.models import Passport

class WeightedScorer(models.Model):
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    weights = models.JSONField(default=dict, blank=True, null=True)


class Score(models.Model):
    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="weighted_scores"
    )
    scorer = models.ForeignKey(WeightedScorer, on_delete=models.PROTECT)
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
