from decimal import Decimal
from typing import Dict, List

import api_logging as logging
from registry.models import Stamp
from scorer_weighted.models import WeightedScorer
from account.models import Customization

log = logging.getLogger(__name__)


def calculate_weighted_score(
    scorer: WeightedScorer, passport_ids: List[int]
) -> List[dict]:
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

    ret: List[dict] = []
    log.debug(
        "calculate_weighted_score for scorer %s and passports %s", scorer, passport_ids
    )
    weights = scorer.weights
    for passport_id in passport_ids:
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        earned_points = {}
        for stamp in Stamp.objects.filter(passport_id=passport_id):
            if stamp.provider not in scored_providers:
                weight = Decimal(weights.get(stamp.provider, 0))
                sum_of_weights += weight
                scored_providers.append(stamp.provider)
                earned_points[stamp.provider] = str(weight)
            else:
                earned_points[stamp.provider] = str(Decimal(0))
        ret.append(
            {
                "sum_of_weights": sum_of_weights,
                "earned_points": earned_points,
            }
        )
    return ret


def recalculate_weighted_score(
    scorer: WeightedScorer, passport_ids: List[int], stamps: Dict[int, List[Stamp]]
) -> List[dict]:
    ret: List[dict] = []
    weights = scorer.weights
    for passport_id in passport_ids:
        stamp_list = stamps.get(passport_id, [])
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        earned_points = {}
        for stamp in stamp_list:
            if stamp.provider not in scored_providers:
                weight = Decimal(weights.get(stamp.provider, 0))
                sum_of_weights += weight
                scored_providers.append(stamp.provider)
                earned_points[stamp.provider] = str(weight)
            else:
                earned_points[stamp.provider] = str(Decimal(0))
        ret.append(
            {
                "sum_of_weights": sum_of_weights,
                "earned_points": earned_points,
            }
        )
    return ret


async def acalculate_weighted_score(
    scorer: WeightedScorer, passport_ids: List[int], community_id: int
) -> List[dict]:
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

    ret: List[dict] = []
    log.debug(
        "calculate_weighted_score for scorer %s and passports %s", scorer, passport_ids
    )
    weights = scorer.weights
    customization = await Customization.objects.aget(scorer_id=community_id)
    if customization:
        weights.update(await customization.aget_customization_dynamic_weights())

    for passport_id in passport_ids:
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        earned_points = {}
        async for stamp in Stamp.objects.filter(passport_id=passport_id):
            if stamp.provider not in scored_providers:
                weight = Decimal(weights.get(stamp.provider, 0))
                sum_of_weights += weight
                scored_providers.append(stamp.provider)
                earned_points[stamp.provider] = float(weight)
            else:
                earned_points[stamp.provider] = float(Decimal(0))

        ret.append(
            {
                "sum_of_weights": sum_of_weights,
                "earned_points": earned_points,
            }
        )
    return ret
