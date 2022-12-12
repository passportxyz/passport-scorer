from django.db import models
from django.conf import settings
import logging
from typing import List

log = logging.getLogger(__name__)

def get_default_weights():
    """
    This function shall provide the default weights for the default scorer.
    It will load the weights from the settings
    """
    log.error("geri settings.GITCOIN_PASSPORT_WEIGHTS %s", settings.GITCOIN_PASSPORT_WEIGHTS)
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

    def compute_score(self) -> List[float]:
        """Compute the score. This shall be overriden in child classes"""
        raise NotImplemented()


class WeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)

    def compute_score(self, passport_ids) -> List[float]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        return calculate_weighted_score(self, passport_ids)


class BinaryWeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(max_digits=10, decimal_places=5)

    def compute_score(self) -> List[float]:
        raise NotImplemented()
