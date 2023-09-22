# TODO: remove pylint skip once circular dependency removed
# pylint: disable=import-outside-toplevel
import json
from decimal import Decimal
from typing import List, Optional, Union

import api_logging as logging
from django.conf import settings
from django.db import models

log = logging.getLogger(__name__)

from ninja_schema import Schema

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
    ):
        self.score = score
        self.evidence = evidence
        self.points = json.dumps(points)

    def __repr__(self):
        return f"ScoreData(score={self.score}, evidence={self.evidence})"


def get_default_weights():
    """
    This function shall provide the default weights for the default scorer.
    It will load the weights from the settings
    """
    return settings.GITCOIN_PASSPORT_WEIGHTS


def get_default_threshold():
    """
    This function shall provide the default threshold for the default binary scorer from the settings.
    """
    return round(Decimal(settings.GITCOIN_PASSPORT_THRESHOLD), THRESHOLD_DECIMAL_PLACES)


class Scorer(models.Model):
    class Type(models.TextChoices):
        WEIGHTED = "WEIGHTED", "Weighted"
        WEIGHTED_BINARY = "WEIGHTED_BINARY", "Weighted Binary"

    type = models.CharField(
        choices=Type.choices,
        default=Type.WEIGHTED,
        max_length=100,
    )

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """Compute the score. This shall be overridden in child classes"""
        raise NotImplemented()

    def __str__(self):
        return f"Scorer #{self.id}, type='{self.type}'"


class WeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        return [
            ScoreData(
                score=s["sum_of_weights"], evidence=None, points=s["earned_points"]
            )
            for s in calculate_weighted_score(self, passport_ids)
        ]

    async def acompute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import acalculate_weighted_score

        scores = await acalculate_weighted_score(self, passport_ids)
        return [
            ScoreData(
                score=s["sum_of_weights"], evidence=None, points=s["earned_points"]
            )
            for s in scores
        ]

    def __str__(self):
        return f"WeightedScorer #{self.id}"


class BinaryWeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(
        max_digits=10,
        decimal_places=THRESHOLD_DECIMAL_PLACES,
        default=get_default_threshold,
    )

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        rawScores = calculate_weighted_score(self, passport_ids)
        binaryScores = [
            Decimal(1) if s["sum_of_weights"] >= self.threshold else Decimal(0)
            for s in rawScores
        ]

        return list(
            map(
                lambda rawScore, binaryScore: ScoreData(
                    score=binaryScore,
                    evidence=[
                        ThresholdScoreEvidence(
                            threshold=Decimal(str(self.threshold)),
                            rawScore=Decimal(rawScore["sum_of_weights"]),
                            success=bool(binaryScore),
                        )
                    ],
                    points=rawScore["earned_points"],
                ),
                rawScores,
                binaryScores,
            )
        )

    async def acompute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import acalculate_weighted_score

        rawScores = await acalculate_weighted_score(self, passport_ids)
        binaryScores = [
            Decimal(1) if s["sum_of_weights"] >= self.threshold else Decimal(0)
            for s in rawScores
        ]

        return list(
            map(
                lambda rawScore, binaryScore: ScoreData(
                    score=binaryScore,
                    evidence=[
                        ThresholdScoreEvidence(
                            threshold=Decimal(str(self.threshold)),
                            rawScore=Decimal(rawScore["sum_of_weights"]),
                            success=bool(binaryScore),
                        )
                    ],
                    points=rawScore["earned_points"],
                ),
                rawScores,
                binaryScores,
            )
        )

    def __str__(self):
        return f"BinaryWeightedScorer #{self.id}, threshold='{self.threshold}'"
