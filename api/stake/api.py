from typing import List

from django.db.models import Q
from ninja_extra import NinjaExtraAPI

import api_logging as logging
from internal.api_key import internal_api_key
from registry.api.utils import is_valid_address, with_read_db
from registry.exceptions import InvalidAddressException, StakingRequestError
from stake.models import Stake
from stake.schema import ErrorMessageResponse, StakeResponse, StakeSchema

log = logging.getLogger(__name__)

# TODO 3280 Remove this api
api = NinjaExtraAPI(urls_namespace="stake")


# Currently no public enabled endpoint for this
# TODO 3280 Remove this endpoint
@api.get(
    "/gtc/{str:address}",
    auth=internal_api_key,
    response={
        200: StakeResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve GTC stake amounts for the GTC Staking stamp",
    description="Get self and community GTC stakes for an address",
)
def get_gtc_stake(request, address: str) -> StakeResponse:
    """
    Get relevant GTC stakes for an address
    """
    return handle_get_gtc_stake(address)


def handle_get_gtc_stake(address: str) -> StakeResponse:
    if not is_valid_address(address):
        raise InvalidAddressException()

    items = get_gtc_stake_for_address(address)
    return StakeResponse(items=items)


def get_gtc_stake_for_address(address: str) -> List[StakeSchema]:
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
