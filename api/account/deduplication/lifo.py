import copy
from typing import Tuple

import api_logging as logging
from account.models import Community
from registry.models import Event, Stamp

log = logging.getLogger(__name__)


# --> LIFO deduplication
async def alifo(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    deduped_passport = copy.deepcopy(lifo_passport)
    deduped_passport["stamps"] = []

    if "stamps" in lifo_passport:
        stamp_hashes = [
            stamp["credential"]["credentialSubject"]["hash"]
            for stamp in lifo_passport["stamps"]
        ]

        clashing_stamps = (
            Stamp.objects.filter(hash__in=stamp_hashes, passport__community=community)
            .exclude(passport__address=address)
            .values("hash", "passport__address", "provider")
        )

        clashing_hashes = {stamp["hash"] async for stamp in clashing_stamps}

        for stamp in lifo_passport["stamps"]:
            if stamp["credential"]["credentialSubject"]["hash"] not in clashing_hashes:
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

        if clashing_stamps.aexists():
            await Event.objects.abulk_create(
                [
                    Event(
                        action=Event.Action.LIFO_DEDUPLICATION,
                        address=address,
                        data={
                            "hash": stamp["hash"],
                            "provider": stamp["provider"],
                            "owner": stamp["passport__address"],
                            "address": address,
                            "community_id": community.pk,
                        },
                    )
                    async for stamp in clashing_stamps
                ]
            )

    return (deduped_passport, None)
