import copy
from typing import Tuple

from django.conf import settings
from django.db import IntegrityError

import api_logging as logging
from account.models import Community
from registry.models import Event, HashScorerLink, Stamp
from registry.utils import get_utc_time

log = logging.getLogger(__name__)


class HashScorerLinkIntegrityError(Exception):
    def __init__(self, message):
        self.message = message or "Issue saving hash scorer links"
        super().__init__(self.message)


async def alifo(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    tries_remaining = 5
    while True:
        try:
            return await arun_lifo_dedup(community, lifo_passport, address)
        except HashScorerLinkIntegrityError:
            tries_remaining -= 1
            # If we get integrity errors from trying to create
            # unique hash links, then we had 2 competing requests
            # and the other one won, so we'll just try again
            # and there should be additional deduplication
            if tries_remaining <= 0:
                raise


def get_nullifiers(stamp: dict) -> list[str]:
    cs = stamp["credential"]["credentialSubject"]
    return [cs["hash"]] if "hash" in cs else cs["nullifiers"]


async def arun_lifo_dedup(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    deduped_passport = copy.deepcopy(lifo_passport)
    deduped_passport["stamps"] = []

    now = get_utc_time()
    if "stamps" in lifo_passport:
        stamp_hashes = []

        for stamp in lifo_passport["stamps"]:
            stamp_hashes.extend(get_nullifiers(stamp))

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
        clashing_stamps = {}

        for stamp in lifo_passport["stamps"]:
            # hash = stamp["credential"]["credentialSubject"]["hash"]
            nullifiers = get_nullifiers(stamp)
            expires_at = stamp["credential"]["expirationDate"]

            if all([hash not in clashing_hashes for hash in nullifiers]):
                deduped_passport["stamps"].append(copy.deepcopy(stamp))
                for hash in nullifiers:
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
                # TODO: geri if not "all" then backfill?
                clashing_stamps[
                    stamp["credential"]["credentialSubject"]["provider"]
                ] = stamp

        await save_hash_links(
            hash_links_to_create, hash_links_to_update, address, community
        )

        if clashing_stamps:
            for hash in get_nullifiers(stamp):
                await Event.objects.abulk_create(
                    [
                        Event(
                            action=Event.Action.LIFO_DEDUPLICATION,
                            address=address,
                            data={
                                "hash": hash,
                                "provider": stamp["credential"]["credentialSubject"][
                                    "provider"
                                ],
                                "community_id": community.pk,
                            },
                            community=community,
                        )
                        for _, stamp in clashing_stamps.items()
                    ]
                )
    return (deduped_passport, None, clashing_stamps)


async def save_hash_links(
    hash_links_to_create: list[HashScorerLink],
    hash_links_to_update: list[HashScorerLink],
    address: str,
    community: Community,
):
    if hash_links_to_create or hash_links_to_update:
        try:
            # Could have IntegrityError if there are conflicting requests
            # running concurrently
            if hash_links_to_create:
                await HashScorerLink.objects.abulk_create(hash_links_to_create)

            if hash_links_to_update:
                await HashScorerLink.objects.abulk_update(
                    hash_links_to_update, fields=["expires_at", "address"]
                )
        except IntegrityError:
            raise HashScorerLinkIntegrityError("Failed to save HashScorerLinks")

        # After updating, double check that there was not a conflicting
        # request that tried to update the same object
        updated_hashes = [hash_link.hash for hash_link in hash_links_to_update]
        created_hashes = [hash_link.hash for hash_link in hash_links_to_create]
        if await HashScorerLink.objects.filter(
            address=address,
            community=community,
            hash__in=(updated_hashes + created_hashes),
        ).acount() != len(hash_links_to_update) + len(hash_links_to_create):
            raise HashScorerLinkIntegrityError("Unexpected number of HashScorerLinks")
