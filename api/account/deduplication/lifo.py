import copy
from typing import Tuple

import api_logging as logging
from account.models import Community
from django.conf import settings
from registry.models import Event, HashScorerLink, Stamp
from registry.utils import get_utc_time

log = logging.getLogger(__name__)


async def alifo(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    if settings.FF_DEDUP_WITH_LINK_TABLE:
        return await alifo_with_link_table(community, lifo_passport, address)
    else:
        return await alifo_with_stamps_table(community, lifo_passport, address)


# --> LIFO deduplication
async def alifo_with_stamps_table(
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

        existing_hash_links = HashScorerLink.objects.filter(
            hash__in=stamp_hashes, community=community
        )

        hash_links_to_create = []
        hash_links_to_update = []

        for stamp in lifo_passport["stamps"]:
            hash = stamp["credential"]["credentialSubject"]["hash"]
            expires_at = stamp["credential"]["expirationDate"]

            if hash not in clashing_hashes:
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

                updated = False
                for hash_link in existing_hash_links:
                    if hash_link.hash == hash:
                        # Update without checking the address or
                        # expiration date, we're just trying to capture
                        # this data in the new table without applying the
                        # new deduplication logic
                        hash_link.address = address
                        hash_link.expires_at = expires_at
                        hash_links_to_update.append(hash_link)
                        updated = True
                        break

                if not updated:
                    hash_links_to_create.append(
                        HashScorerLink(
                            hash=hash,
                            address=address,
                            community=community,
                            expires_at=expires_at,
                        )
                    )

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

        if hash_links_to_create:
            await HashScorerLink.objects.abulk_create(hash_links_to_create)

        if hash_links_to_update:
            await HashScorerLink.objects.abulk_update(
                hash_links_to_update, fields=["expires_at", "address"]
            )

    return (deduped_passport, None)


async def alifo_with_link_table(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    deduped_passport = copy.deepcopy(lifo_passport)
    deduped_passport["stamps"] = []

    now = get_utc_time()
    if "stamps" in lifo_passport:
        stamp_hashes = [
            stamp["credential"]["credentialSubject"]["hash"]
            for stamp in lifo_passport["stamps"]
        ]

        existing_hash_links = HashScorerLink.objects.filter(
            hash__in=stamp_hashes, community=community
        )

        existing_user_hash_links, clashing_hashes, forfeited_hash_links = [], [], []
        async for hash_link in existing_hash_links:
            if hash_link.address == address:
                existing_user_hash_links.append(hash_link)
            elif hash_link.expires_at > now:
                clashing_hashes.append(hash_link.hash)
            else:
                # Already claimed by another user,
                # but it's expired so we'll give it to the new user
                forfeited_hash_links.append(hash_link)

        hash_links_to_create = []
        hash_links_to_update = []
        clashing_stamps = []

        for stamp in lifo_passport["stamps"]:
            hash = stamp["credential"]["credentialSubject"]["hash"]
            expires_at = stamp["credential"]["expirationDate"]

            if hash not in clashing_hashes:
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

                updated = False
                forfeited = False

                for existing_hash_link in existing_user_hash_links:
                    if existing_hash_link.hash == hash:
                        existing_hash_link.expires_at = expires_at
                        hash_links_to_update.append(existing_hash_link)
                        updated = True
                        break

                if not updated:
                    for forfeited_hash in forfeited_hash_links:
                        if forfeited_hash.hash == hash:
                            forfeited_hash.address = address
                            forfeited_hash.expires_at = expires_at
                            hash_links_to_update.append(forfeited_hash)
                            forfeited = True
                            break

                if not forfeited and not updated:
                    hash_links_to_create.append(
                        HashScorerLink(
                            hash=hash,
                            address=address,
                            community=community,
                            expires_at=stamp["credential"]["expirationDate"],
                        )
                    )
            else:
                clashing_stamps.append(stamp)

        if clashing_stamps:
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
                    for stamp in clashing_stamps
                ]
            )

        if hash_links_to_create:
            await HashScorerLink.objects.abulk_create(hash_links_to_create)

        if hash_links_to_update:
            await HashScorerLink.objects.abulk_update(
                hash_links_to_update, fields=["expires_at", "address"]
            )

    return (deduped_passport, None)


from django.core.paginator import Paginator

paginator = Paginator(Stamp.objects.select_related("passport").all(), 1000)

for page in paginator.page_range:
    hash_links = [
        HashScorerLink(
            hash=stamp.hash,
            address=stamp.passport.address,
            community=stamp.passport.community,
            expires_at=stamp.credential["expirationDate"],
        )
        for stamp in paginator.page(page).object_list
    ]


## 1. Migrate to create table
## 2. Update code which writes to new table without respecting new rules for dedup
## 3. Populate with historical data, overwiring lines that fail uniqueness constraints (this will cause issues only for people taking advantage of this)
## 4. Turn on FF to use new dedup logic
