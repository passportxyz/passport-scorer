from datetime import datetime
from decimal import Decimal
from math import e
from typing import Dict, List

import api_logging as logging
from account.models import Customization
from registry.models import Stamp
from scorer_weighted.models import WeightedScorer

log = logging.getLogger(__name__)


def calculate_weighted_score(
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

    try:
        customization = Customization.objects.get(scorer_id=community_id)
        weights.update(customization.get_customization_dynamic_weights())
    except Customization.DoesNotExist:
        pass

    for passport_id in passport_ids:
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        earned_points = {}
        earliest_expiration_date = None
        stamp_expiration_dates = {}
        for stamp in Stamp.objects.filter(passport_id=passport_id):
            if stamp.provider not in scored_providers:
                weight = Decimal(weights.get(stamp.provider, 0))
                sum_of_weights += weight
                scored_providers.append(stamp.provider)
                earned_points[stamp.provider] = str(weight)
                expiration_date = datetime.fromisoformat(
                    stamp.credential["expirationDate"]
                )
                stamp_expiration_dates[stamp.provider] = expiration_date
                # Compute the earliest expiration date for the stamps used to calculate the score
                # as this will be the expiration date of the score
                if (
                    not earliest_expiration_date
                    or expiration_date < earliest_expiration_date
                ):
                    earliest_expiration_date = expiration_date
            else:
                earned_points[stamp.provider] = str(Decimal(0))
        ret.append(
            {
                "sum_of_weights": sum_of_weights,
                "earned_points": earned_points,
                "expiration_date": earliest_expiration_date,
                "stamp_expiration_dates": stamp_expiration_dates,
            }
        )
    return ret


def recalculate_weighted_score(
    scorer: WeightedScorer,
    passport_ids: List[int],
    stamps: Dict[int, List[Stamp]],
    community_id: int,
) -> List[dict]:
    ret: List[dict] = []
    weights = scorer.weights

    try:
        customization = Customization.objects.get(scorer_id=community_id)
        weights.update(customization.get_customization_dynamic_weights())
    except Customization.DoesNotExist:
        pass

    for passport_id in passport_ids:
        stamp_list = stamps.get(passport_id, [])
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        earned_points = {}
        earliest_expiration_date = None
        stamp_expiration_dates = {}
        for stamp in stamp_list:
            if stamp.provider not in scored_providers:
                weight = Decimal(weights.get(stamp.provider, 0))
                sum_of_weights += weight
                scored_providers.append(stamp.provider)
                earned_points[stamp.provider] = str(weight)
                expiration_date = datetime.fromisoformat(
                    stamp.credential["expirationDate"]
                )
                stamp_expiration_dates[stamp.provider] = expiration_date
                # Compute the earliest expiration date for the stamps used to calculate the score
                # as this will be the expiration date of the score
                if (
                    not earliest_expiration_date
                    or expiration_date < earliest_expiration_date
                ):
                    earliest_expiration_date = expiration_date
            else:
                earned_points[stamp.provider] = str(Decimal(0))
        ret.append(
            {
                "sum_of_weights": sum_of_weights,
                "earned_points": earned_points,
                "expiration_date": earliest_expiration_date,
                "stamp_expiration_dates": stamp_expiration_dates,
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

    try:
        customization = await Customization.objects.aget(scorer_id=community_id)
        weights.update(await customization.aget_customization_dynamic_weights())
    except Customization.DoesNotExist:
        pass

    for passport_id in passport_ids:
        sum_of_weights: Decimal = Decimal(0)
        scored_providers = []
        earned_points = {}
        stamp_expiration_dates = {}
        earliest_expiration_date = None
        async for stamp in Stamp.objects.filter(passport_id=passport_id):
            if stamp.provider not in scored_providers:
                weight = Decimal(weights.get(stamp.provider, 0))
                sum_of_weights += weight
                scored_providers.append(stamp.provider)
                earned_points[stamp.provider] = float(weight)
                expiration_date = datetime.fromisoformat(
                    stamp.credential["expirationDate"]
                )
                stamp_expiration_dates[stamp.provider] = expiration_date
                # Compute the earliest expiration date for the stamps used to calculate the score
                # as this will be the expiration date of the score
                if (
                    not earliest_expiration_date
                    or expiration_date < earliest_expiration_date
                ):
                    earliest_expiration_date = expiration_date
            else:
                earned_points[stamp.provider] = float(Decimal(0))

        ret.append(
            {
                "sum_of_weights": sum_of_weights,
                "earned_points": earned_points,
                "expiration_date": earliest_expiration_date,
                "stamp_expiration_dates": stamp_expiration_dates,
            }
        )
    return ret
