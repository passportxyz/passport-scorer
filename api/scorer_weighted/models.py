from django.db import models
from django.conf import settings


def get_default_parent_scorer_for_weighted():
    return Scorer(type=Scorer.Type.WEIGHTED)


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
        choices=[
            (Type.WEIGHTED, "Weighted"),
            (Type.WEIGHTED_BINARY, "Weighted Binary"),
        ],
        default=Type.WEIGHTED,
        max_length=100,
    )

    def compute_score(self):
        raise NotImplemented()


class WeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)

    def compute_score(self):
        raise NotImplemented()


class BinaryWeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(max_digits=10, decimal_places=5)

    def compute_score(self):
        raise NotImplemented()
