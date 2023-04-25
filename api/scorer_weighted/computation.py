from datetime import datetime
from decimal import Decimal
from typing import List

import api_logging as logging
from scorer_weighted.models import WeightedScorer

log = logging.getLogger(__name__)


def calculate_weighted_score(
    scorer: WeightedScorer, passport_ids: List[int]
) -> List[Decimal]:
    """
    Calculate the weighted score for the given list of passport IDs and a single scorer.

    This function retrieves the weights for the scorer, filters the stamps associated
    with each passport ID, and calculates the weighted score based on the weights of
    the stamps. The weight of each stamp is determined by the scorer's weights dict.

    Args:
        scorer (WeightedScorer): The scorer to use for calculating the weighted score.
        passport_ids (List[int]): A list of passport IDs to calculate the weighted score for.

    Returns:
        A list of Decimal values representing the weighted scores for the given passport IDs.
    """
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
