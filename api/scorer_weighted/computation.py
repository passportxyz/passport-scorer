import logging
from datetime import datetime
from decimal import Decimal
from typing import List

from scorer_weighted.models import WeightedScorer

log = logging.getLogger(__name__)


# pylint: disable=unused-argument
def calculate_score(sender, passport_ids, **kwargs):
    now = datetime.now()
    log.debug("calculate_score has been triggered for %s", passport_ids)
    for scorer in WeightedScorer.objects.filter(start_time__lte=now, end_time__gt=now):
        calculate_weighted_score(scorer, passport_ids)


def calculate_weighted_score(
    scorer: WeightedScorer, passport_ids: List[int]
) -> List[Decimal]:
    from registry.models import Stamp

    ret: List[Decimal] = []
    log.debug(
        "calculate_weighted_score for scorer %s and passports %s", scorer, passport_ids
    )
    weights = scorer.weights
    for passport_id in passport_ids:
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        for stamp in Stamp.objects.filter(passport_id=passport_id):
            if stamp.provider not in scored_providers:
                sum_of_weights += Decimal(weights.get(stamp.provider, 0))
                scored_providers.append(stamp.provider)
        ret.append(sum_of_weights)
    return ret
