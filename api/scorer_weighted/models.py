# TODO: remove pylint skip once circular dependency removed
# pylint: disable=import-outside-toplevel
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from django.conf import settings
from django.db import models

import api_logging as logging
from registry.weight_models import WeightConfiguration, WeightConfigurationItem

log = logging.getLogger(__name__)


THRESHOLD_DECIMAL_PLACES = 5


class ThresholdScoreEvidence:
    def __init__(self, success: bool, rawScore: Decimal, threshold: Decimal):
        self.type = "ThresholdScoreCheck"
        self.success = success
        self.rawScore = rawScore
        self.threshold = threshold

    def as_dict(self):
        return {
            "type": self.type,
            "success": self.success,
            "rawScore": str(self.rawScore),
            "threshold": str(self.threshold),
        }

    def __repr__(self):
        return f"ThresholdScoreEvidence(success={self.success}, rawScore={self.rawScore}, threshold={self.threshold})"


class ScoreData:
    # do multiple evidence types like:
    # Optional[List[Union[ThresholdScoreEvidence, RequiredStampEvidence]]]
    def __init__(
        self,
        score: Decimal,
        evidence: Optional[List[ThresholdScoreEvidence]],
        points: dict,
        expiration_date: datetime,
        stamp_expiration_dates: dict,
    ):
        self.score = score
        self.evidence = evidence
        self.stamp_scores = points
        self.expiration_date = expiration_date
        self.stamp_expiration_dates = stamp_expiration_dates

    def __repr__(self):
        return f"ScoreData(score={self.score}, evidence={self.evidence})"


def get_default_weights():
    """
    This function shall provide the default weights for the default scorer.
    It will load the weights from the settings
    """
    return WeightConfigurationItem.get_active_weights()


def get_default_threshold():
    """
    This function shall provide the default threshold for the default binary scorer from the settings.
    """
    try:
        return WeightConfiguration.get_active_threshold()
    except Exception as e:
        log.error(f"Failed to get default threshold: {e}")
        return 20


class Scorer(models.Model):
    class Type(models.TextChoices):
        WEIGHTED = "WEIGHTED", "Weighted"
        WEIGHTED_BINARY = "WEIGHTED_BINARY", "Weighted Binary"

    type = models.CharField(
        choices=Type.choices,
        default=Type.WEIGHTED,
        max_length=100,
    )

    exclude_from_weight_updates = models.BooleanField(
        default=False,
        help_text="If true, this scorer will be excluded from automatic weight updates and associated rescores",
    )

    def compute_score(self, passport_ids, community_id: int) -> List[ScoreData]:
        """Compute the score. This shall be overridden in child classes"""
        raise NotImplementedError()

    def __str__(self):
        return f"Scorer #{self.id}, type='{self.type}'"


# Both scorer now use the same logic, defined here
class BinaryWeightedScorerMixin:
    def _score_to_binary(self, sum_of_weights):
        return Decimal(1) if sum_of_weights >= self.threshold else Decimal(0)

    def _make_score_data(self, rawScores, binaryScores):
        return [
            ScoreData(
                score=binaryScore,
                evidence=[
                    ThresholdScoreEvidence(
                        threshold=Decimal(str(self.threshold)),
                        rawScore=Decimal(rawScore["sum_of_weights"]),
                        success=bool(binaryScore),
                    )
                ],
                points=rawScore["earned_points"],
                expiration_date=rawScore["expiration_date"],
                stamp_expiration_dates=rawScore["stamp_expiration_dates"],
            )
            for rawScore, binaryScore in zip(rawScores, binaryScores)
        ]

    def compute_score(self, passport_ids, community_id: int) -> List[ScoreData]:
        from .computation import calculate_weighted_score
        rawScores = calculate_weighted_score(self, passport_ids, community_id)
        binaryScores = [self._score_to_binary(s["sum_of_weights"]) for s in rawScores]
        return self._make_score_data(rawScores, binaryScores)

    def recompute_score(self, passport_ids, stamps, community_id: int) -> List[ScoreData]:
        from .computation import recalculate_weighted_score
        rawScores = recalculate_weighted_score(self, passport_ids, stamps, community_id)
        binaryScores = [self._score_to_binary(s["sum_of_weights"]) for s in rawScores]
        return self._make_score_data(rawScores, binaryScores)

    async def acompute_score(self, passport_ids, community_id: int) -> List[ScoreData]:
        from .computation import acalculate_weighted_score
        rawScores = await acalculate_weighted_score(self, passport_ids, community_id)
        binaryScores = [self._score_to_binary(s["sum_of_weights"]) for s in rawScores]
        return self._make_score_data(rawScores, binaryScores)


# This is now exactly the same as BinaryWeightedScorer, just kept here
# for backwards compatibility with the score format for the registry api.
# If we ever fully deprecate the registry API and use only /v2/, we
# can remove this model and migrate everybody to a BinaryWeightedScorer
class WeightedScorer(BinaryWeightedScorerMixin, Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(
        max_digits=10,
        decimal_places=THRESHOLD_DECIMAL_PLACES,
        default=get_default_threshold,
    )

    def __str__(self):
        return f"WeightedScorer #{self.id}, threshold='{self.threshold}'"


class BinaryWeightedScorer(BinaryWeightedScorerMixin, Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(
        max_digits=10,
        decimal_places=THRESHOLD_DECIMAL_PLACES,
        default=get_default_threshold,
    )

    def __str__(self):
        return f"BinaryWeightedScorer #{self.id}, threshold='{self.threshold}'"


class RescoreRequest(models.Model):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    status = models.CharField(
        choices=Status.choices,
        default=Status.RUNNING,
        max_length=20,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    num_communities_requested = models.IntegerField(default=0)
    num_communities_processed = models.IntegerField(default=0)

    def __str__(self):
        return f"RescoreRequest #{self.pk}, status='{self.status}', created_at='{self.created_at}'"
