import copy
from typing import Tuple

import api_logging as logging
from account.models import Community
from registry.models import Event, Stamp

log = logging.getLogger(__name__)


# --> FIFO deduplication
async def afifo(
    community: Community, fifo_passport: dict, address: str
) -> Tuple[dict, list]:
    deduped_passport = copy.deepcopy(fifo_passport)
    affected_passports = []
    if "stamps" in fifo_passport:
        dedup_event_data = []
        new_stamp_hashes = [
            stamp["credential"]["credentialSubject"]["hash"]
            for stamp in fifo_passport["stamps"]
        ]

        existing_stamps = (
            Stamp.objects.filter(
                hash__in=new_stamp_hashes, passport__community=community
            )
            .exclude(passport__address=address)
            .select_related("passport")
        )

        async for existing_stamp in existing_stamps:
            existing_stamp_passport = existing_stamp.passport
            affected_passports.append(existing_stamp_passport)
            dedup_event_data.append(
                {
                    "hash": existing_stamp.hash,
                    "provider": existing_stamp.provider,
                    "prev_owner": existing_stamp_passport.address,
                    "address": address,
                    "community_id": community.pk,
                }
            )

        await existing_stamps.adelete()

        if dedup_event_data:
            await Event.objects.abulk_create(
                [
                    Event(
                        action=Event.Action.FIFO_DEDUPLICATION,
                        address=data["prev_owner"],
                        data=data,
                    )
                    for data in dedup_event_data
                ]
            )

    return (deduped_passport, affected_passports)
