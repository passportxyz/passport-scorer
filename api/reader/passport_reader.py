# libs for processing the deterministic stream location
from typing import Dict, List, Set, TypedDict

from asgiref.sync import async_to_sync

import api_logging as logging
from ceramic_cache.models import CeramicCache

log = logging.getLogger(__name__)


class StampOverride(TypedDict):
    preferred: str
    overridden: str


STAMP_OVERRIDES: List[StampOverride] = [
    {
        "preferred": "CoinbaseDualVerification",
        "overridden": "CoinbaseDualVerification2",
    },
    {"preferred": "BinanceBABT", "overridden": "BinanceBABT2"},
]

# Quick lookup map
OVERRIDDEN_TO_PREFERRED_PROVIDER = {
    override["overridden"]: override["preferred"] for override in STAMP_OVERRIDES
}


# Ceramic definition id for Gitcoin Passport
CERAMIC_GITCOIN_PASSPORT_STREAM_ID = (
    "kjzl6cwe1jw148h1e14jb5fkf55xmqhmyorp29r9cq356c7ou74ulowf8czjlzs"
)


def get_did(address, network="1"):
    # returns the did associated with the address on the given network
    return (f"did:pkh:eip155:{network}:{address}").lower()


# Overridden if the provider is listed as a overridden provider and
# the preferred provider is in the current list of all
# providers for this user
def is_overridden(provider: str, all_user_providers: Set[str]) -> bool:
    return (
        provider in OVERRIDDEN_TO_PREFERRED_PROVIDER
        and OVERRIDDEN_TO_PREFERRED_PROVIDER[provider] in all_user_providers
    )


def filter_conflicting_stamps(stamps: List[CeramicCache]) -> List[CeramicCache]:
    providers = set([stamp.provider for stamp in stamps])

    return [stamp for stamp in stamps if not is_overridden(stamp.provider, providers)]


async def aget_passport(address: str = "") -> Dict:
    db_stamp_list = CeramicCache.objects.filter(
        address=address, deleted_at__isnull=True, revocation__isnull=True
    )

    stamps_by_provider = dict()

    async for stamp in db_stamp_list:
        if stamp.provider not in stamps_by_provider:
            stamps_by_provider[stamp.provider] = []

        stamps_by_provider[stamp.provider].append(stamp)

    latest_stamps = []

    for provider in stamps_by_provider:
        latest_date = None
        latest_stamp = None
        for stamp in stamps_by_provider[provider]:
            if latest_date is None or stamp.updated_at > latest_date:
                latest_date = stamp.updated_at
                latest_stamp = stamp

        latest_stamps.append(latest_stamp)

    filtered_stamps = filter_conflicting_stamps(latest_stamps)

    return {
        "stamps": [
            {"provider": s.provider, "credential": s.stamp} for s in filtered_stamps
        ]
    }


def get_passport(address: str = "") -> Dict:
    return async_to_sync(aget_passport)(address)
