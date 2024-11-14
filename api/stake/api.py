from typing import List

from django.db.models import Q
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from registry.api.utils import is_valid_address, with_read_db
from registry.exceptions import InvalidAddressException, StakingRequestError
from stake.models import Stake
from stake.schema import ErrorMessageResponse, GetSchemaResponse, StakeSchema
from trusta_labs.api import CgrantsApiKey

secret_key = CgrantsApiKey()

log = logging.getLogger(__name__)

api = NinjaExtraAPI(urls_namespace="stake")


@api.get(
    "/gtc/{str:address}",
    auth=secret_key,
    response={
        200: GetSchemaResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve GTC stake amounts for the GTC Staking stamp",
    description="Get self and community GTC stakes for an address",
)
def get_gtc_stake(request, address: str) -> GetSchemaResponse:
    """
    Get relevant GTC stakes for an address
    """
    if not is_valid_address(address):
        raise InvalidAddressException()

    get_stake_response = handle_get_gtc_stake(address)
    response = GetSchemaResponse(items=get_stake_response)
    return response


def handle_get_gtc_stake(address: str) -> List[StakeSchema]:
    address = address.lower()

    try:
        return [
            StakeSchema(
                chain=stake.chain,
                staker=stake.staker,
                stakee=stake.stakee,
                amount=stake.current_amount,
                lock_time=stake.lock_time.isoformat(),
                unlock_time=stake.unlock_time.isoformat(),
                last_updated_in_block=stake.last_updated_in_block,
            )
            for stake in with_read_db(Stake).filter(
                Q(staker=address) | Q(stakee=address)
            )
        ]
    except Exception:
        log.exception("Error getting GTC stakes")
        raise StakingRequestError()
