from typing import List

from django.db.models import Q

import api_logging as logging
from registry.api.utils import is_valid_address, with_read_db
from registry.exceptions import InvalidAddressException, StakingRequestError
from stake.models import Stake
from stake.schema import StakeResponse, StakeSchema

log = logging.getLogger(__name__)

# Endpoint for this defined in internal module
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
