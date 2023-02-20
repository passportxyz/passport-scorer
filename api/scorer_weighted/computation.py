import logging
from datetime import datetime
from decimal import Decimal
from typing import List

from scorer_weighted.models import WeightedScorer

log = logging.getLogger(__name__)


# pylint: disable=unused-argument
def calculate_score(sender, passport_ids, **kwargs):
    """
    Calculate the score for the given list of passport IDs.
    
    This function retrieves the weighted scorers that are active at the time of
    the function call and calculates the weighted score for each passport ID
    in the input list by calling `calculate_weighted_score`.
    
    Args:
        sender: The sender of the signal that triggered the function call.
        passport_ids (List[int]): A list of passport IDs to calculate the score for.
        **kwargs: Additional keyword arguments that are ignored.
    """
    now = datetime.now()
    log.debug("calculate_score has been triggered for %s", passport_ids)
    for scorer in WeightedScorer.objects.filter(start_time__lte=now, end_time__gt=now):
        calculate_weighted_score(scorer, passport_ids)


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
