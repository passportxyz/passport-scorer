import logging
from datetime import datetime
from typing import List

from registry.models import Stamp
from scorer_weighted.models import Score, WeightedScorer

log = logging.getLogger(__name__)


# pylint: disable=unused-argument
def calculate_score(sender, passport_ids, **kwargs):
    now = datetime.now()
    log.debug("calculate_score has been triggered for %s", passport_ids)
    for scorer in WeightedScorer.objects.filter(start_time__lte=now, end_time__gt=now):
        calculate_weighted_score(scorer, passport_ids)


def calculate_weighted_score(scorer: WeightedScorer, passport_ids: List[int]):
    log.debug(
        "calculate_weighted_score for scorer %s and passports %s", scorer, passport_ids
    )
    weights = scorer.weights
    for passport_id in passport_ids:
        sum_of_weights = 0
        for stamp in Stamp.objects.filter(passport_id=passport_id):
            sum_of_weights += weights.get(stamp.provider, 0)
        Score.objects.update_or_create(
            passport_id=passport_id, scorer=scorer, defaults=dict(score=sum_of_weights)
        )
