# TODO: remove pylint skip once circular dependency removed
# pylint: disable=import-outside-toplevel
import logging
from typing import List, Union, Optional

from django.conf import settings
from django.db import models

log = logging.getLogger(__name__)

from ninja_schema import Schema

# TODO Perhaps we should use normal types here instead of
# schemas, but then we'd have to redefine the schemas in
# the API code. But maybe that's best. Alternatively,
# maybe we keep it as Schema and add evidence to the DB


class ScoreEvidence(Schema):
    type: str
    success: bool


class ThresholdEvidence(ScoreEvidence):
    rawScore: str
    threshold: str


class RequiredStampEvidence(ScoreEvidence):
    stamp: str


class ScoreData(Schema):
    score: str
    evidence: Optional[List[Union[ThresholdEvidence, RequiredStampEvidence]]]


def get_default_weights():
    """
    This function shall provide the default weights for the default scorer.
    It will load the weights from the settings
    """
    return settings.GITCOIN_PASSPORT_WEIGHTS


class Scorer(models.Model):
    class Type(models.TextChoices):
        WEIGHTED = "WEIGHTED", "Weighted"
        WEIGHTED_BINARY = "WEIGHTED_BINARY", "Weighted Binary"

    type = models.CharField(
        choices=Type.choices,
        default=Type.WEIGHTED,
        max_length=100,
    )

    def compute_score(self) -> List[ScoreData]:
        """Compute the score. This shall be overriden in child classes"""
        raise NotImplemented()


class WeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        return [
            ScoreData(score=str(s), evidence=None)
            for s in calculate_weighted_score(self, passport_ids)
        ]


class BinaryWeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(max_digits=10, decimal_places=5)

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        rawScores = calculate_weighted_score(self, passport_ids)
        binaryScores = ["1" if s >= self.threshold else "0" for s in rawScores]

        return list(
            map(
                lambda rawScore, binaryScore: ScoreData(
                    score=binaryScore,
                    evidence=list(
                        [
                            ThresholdEvidence(
                                type="thresholdScore",
                                threshold=str(self.threshold),
                                rawScore=str(rawScore),
                                success=(binaryScore == "1"),
                            )
                        ]
                    ),
                ),
                rawScores,
                binaryScores,
            )
        )
