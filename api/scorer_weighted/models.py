from django.db import models
from django.conf import settings

from registry.models import Passport


def get_default_weights():
    """
    This function shall provide the default weights for the default scorer.
    It will load the weights from the settings
    """
    return settings.GITCOIN_PASSPORT_WEIGHTS


class Scorer(models.Model):
    class Type:
        WEIGHTED = "WEIGHTED"
        WEIGHTED_BINARY = "WEIGHTED_BINARY"

    type = models.CharField(
        choices=[(Type.WEIGHTED, "Weighted"), (Type.WEIGHTED_BINARY, "Weighted Binary")]
    )

    def compute_score(sefl):
        raise NotImplemented()


class WeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)

    def compute_score(self):
        raise NotImplemented()


class BinaryWeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(max_digits=10, decimal_places=5)

    def compute_score(sefl):
        raise NotImplemented()


class Score(models.Model):
    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="score"
    )
    scorer = models.ForeignKey(Scorer, on_delete=models.PROTECT)
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
