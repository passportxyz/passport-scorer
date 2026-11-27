# libs for processing the deterministic stream location
from typing import Dict, List

from asgiref.sync import async_to_sync
from django.db.models import F
from django.db.models.fields.json import KT

import api_logging as logging
from ceramic_cache.models import CeramicCache

log = logging.getLogger(__name__)


# Ceramic definition id for Gitcoin Passport
CERAMIC_GITCOIN_PASSPORT_STREAM_ID = (
    "kjzl6cwe1jw148h1e14jb5fkf55xmqhmyorp29r9cq356c7ou74ulowf8czjlzs"
)


def get_did(address, network="1"):
    # returns the did associated with the address on the given network
    return (f"did:pkh:eip155:{network}:{address}").lower()


async def aget_passport(address: str = "", *, chain_id: int | None = None) -> Dict:
    db_stamp_list = CeramicCache.objects.filter(
        address=address, deleted_at__isnull=True, revocation__isnull=True
    )

    if chain_id is not None:
        # Scope before choosing the latest stamp. Another chain can have a
        # more recent stamp from the same provider at the same hex address.
        db_stamp_list = (
            db_stamp_list.alias(
                subject_provider=KT("stamp__credentialSubject__provider")
            )
            .filter(
                stamp__credentialSubject__id__iexact=get_did(address, str(chain_id)),
                subject_provider=F("provider"),
            )
            .order_by("id")
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

    return {
        "stamps": [
            {"provider": s.provider, "credential": s.stamp} for s in latest_stamps
        ]
    }


def get_passport(address: str = "") -> Dict:
    return async_to_sync(aget_passport)(address)
