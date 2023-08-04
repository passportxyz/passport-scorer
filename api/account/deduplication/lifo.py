import copy
from typing import Tuple

import api_logging as logging
from account.models import Community
from django.conf import settings
from django.db import IntegrityError
from registry.models import Event, HashScorerLink, Stamp
from registry.utils import get_utc_time

log = logging.getLogger(__name__)


class HashScorerLinkIntegrityError(Exception):
    pass


async def alifo(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    tries_remaining = 5
    while True:
        try:
            return await run_correct_alifo_version(community, lifo_passport, address)
        except HashScorerLinkIntegrityError:
            tries_remaining -= 1
            # If we get integrity errors from trying to create
            # unique hash links, then we had 2 competing requests
            # and the other one won, so we'll just try again
            # and there should be additional deduplication
            if tries_remaining <= 0:
                raise


# TODO once this is fully released, we can
# 1. remove the _stamp_table function, the FF, and the update function below
# 2. rename the _link_table function
async def run_correct_alifo_version(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    if settings.FF_DEDUP_WITH_LINK_TABLE == "on":
        return await alifo_with_link_table(community, lifo_passport, address)
    else:
        return await alifo_with_stamp_table(community, lifo_passport, address)


# --> LIFO deduplication
async def alifo_with_stamp_table(
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

                done = False
                async for hash_link in existing_hash_links:
                    if hash_link.hash == hash:
                        # Update without checking the address or
                        # expiration date, we're just trying to capture
                        # this data in the new table without applying the
                        # new deduplication logic
                        hash_link.address = address
                        hash_link.expires_at = expires_at
                        hash_links_to_update.append(hash_link)
                        done = True
                        break

                if not done:
                    hash_links_to_create.append(
                        HashScorerLink(
                            hash=hash,
                            address=address,
                            community=community,
                            expires_at=expires_at,
                        )
                    )

        await save_hash_links(
            hash_links_to_create, hash_links_to_update, address, community
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

        this_users_hash_links, clashing_hashes, forfeited_hash_links = [], [], []
        async for hash_link in existing_hash_links:
            if hash_link.address == address:
                # Already claimed by this user,
                this_users_hash_links.append(hash_link)
            elif hash_link.expires_at > now:
                # Already claimed by another user,
                clashing_hashes.append(hash_link.hash)
            else:
                # Already claimed by another user, but
                # it's expired so we'll give it to this user
                forfeited_hash_links.append(hash_link)

        hash_links_to_create = []
        hash_links_to_update = []
        clashing_stamps = []

        for stamp in lifo_passport["stamps"]:
            hash = stamp["credential"]["credentialSubject"]["hash"]
            expires_at = stamp["credential"]["expirationDate"]

            if hash not in clashing_hashes:
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

                done = False

                for hash_link in this_users_hash_links:
                    if hash_link.hash == hash:
                        done = True
                        if hash_link.expires_at != expires_at:
                            hash_link.expires_at = expires_at
                            hash_links_to_update.append(hash_link)
                        break

                if not done:
                    for hash_link in forfeited_hash_links:
                        if hash_link.hash == hash:
                            done = True
                            hash_link.address = address
                            hash_link.expires_at = expires_at
                            hash_links_to_update.append(hash_link)
                            break

                if not done:
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

        await save_hash_links(
            hash_links_to_create, hash_links_to_update, address, community
        )

        if clashing_stamps:
            await Event.objects.abulk_create(
                [
                    Event(
                        action=Event.Action.LIFO_DEDUPLICATION,
                        address=address,
                        data={
                            "hash": stamp["credential"]["credentialSubject"]["hash"],
                            "provider": stamp["credential"]["credentialSubject"][
                                "provider"
                            ],
                            "community_id": community.pk,
                        },
                    )
                    for stamp in clashing_stamps
                ]
            )

    return (deduped_passport, None)


async def save_hash_links(
    hash_links_to_create: list[HashScorerLink],
    hash_links_to_update: list[HashScorerLink],
    address: str,
    community: Community,
):
    if hash_links_to_create or hash_links_to_update:
        try:
            # Do the create first, because this is where we
            # might have IntegrityErrors and we don't want to
            # update the existing objects if there's an issue
            if hash_links_to_create:
                await HashScorerLink.objects.abulk_create(hash_links_to_create)

            if hash_links_to_update:
                await HashScorerLink.objects.abulk_update(
                    hash_links_to_update, fields=["expires_at", "address"]
                )
        except IntegrityError:
            raise HashScorerLinkIntegrityError()

        # After saving, double check that there was not a conflicting
        # request that tried to update the same object
        if await HashScorerLink.objects.filter(
            address=address, community=community
        ).acount() != len(hash_links_to_create) + len(hash_links_to_update):
            raise HashScorerLinkIntegrityError()


# TODO this can be deleted in the next release
def update_to_be_run_once_manually():
    from django.core.paginator import Paginator

    now = get_utc_time()
    paginator = Paginator(Stamp.objects.select_related("passport").all(), 1000)

    for page in paginator.page_range:
        print(f"Page {page} of {paginator.num_pages}")
        hash_links = [
            HashScorerLink(
                hash=stamp.hash,
                address=stamp.passport.address,
                community=stamp.passport.community,
                expires_at=stamp.credential["expirationDate"],
            )
            for stamp in paginator.page(page).object_list
            if stamp.credential["expirationDate"] > now
        ]
        HashScorerLink.objects.bulk_create(hash_links, ignore_conflicts=True)


## 1. Migrate to create table
## 2. Update code which writes to new table without respecting new rules for dedup
##    This is just to support new stamps that come in while the update is running
## 3. Populate with historical data, ignoring lines that fail uniqueness constraints
##    If there's a uniqueness issue, this user has used the same hash with multiple addresses
##    and a random one of them will end up with the stamp
## 4. Turn on FF to use new dedup logic
