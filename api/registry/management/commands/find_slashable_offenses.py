from datetime import datetime, timedelta, timezone
from typing import List, Optional

from ceramic_cache.models import CeramicCache
from django.conf import settings
from django.core.management.base import BaseCommand
from registry.models import Event, HashScorerLink, Slash, SlashBatch
from tqdm import tqdm

QUERY_BATCH_SIZE = 1000


class StakeToSlash:
    def __init__(
        self, staker: str, stakee: str, offender: Slash.OffenderChoices.choices
    ):
        self.staker = staker
        self.stakee = stakee
        self.offender = offender


class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.now()
        now = now.replace(tzinfo=timezone.utc)

        offender_addresses = self.get_offender_addresses(now)

        self.create_slash_records(offender_addresses)

        self.stdout.write(f"Done")

    def get_offender_addresses(self, now: datetime) -> Optional[List[str]]:
        dedup_community_id = settings.CERAMIC_CACHE_SCORER_ID
        three_months_ago = now - timedelta(days=90)

        self.stdout.write(
            f"Finding Addresses involved in deduplication for community {dedup_community_id}"
        )

        addresses = []

        with tqdm(
            unit="records", unit_scale=True, desc="Processing deduplication records"
        ) as progress_bar:
            last_id = 0
            while True:
                # Fetch a batch of records
                records = Event.objects.filter(
                    community_id=dedup_community_id,
                    id__gt=last_id,
                    action=Event.Action.LIFO_DEDUPLICATION,
                    # limit to the last 3 months assuming any record that may exist would be expired anyways
                    created_at__gt=three_months_ago,
                ).order_by("id")[:QUERY_BATCH_SIZE]

                if not records:
                    break

                relevant_hash_scorer_links = HashScorerLink.objects.filter(
                    community_id=dedup_community_id,
                    hash__in=[
                        record.data.get("hash")
                        for record in records
                        if record.data.get("hash")
                    ],
                )

                original_holder_for_hash = {
                    link.hash: link.address for link in relevant_hash_scorer_links
                }

                flagged_address_provider_pairs = []
                for record in records:
                    flagged_address_provider_pairs.append(
                        (record.address, record.data.get("provider"))
                    )
                    original_holder_address = original_holder_for_hash.get(
                        record.data.get("hash")
                    )
                    flagged_address_provider_pairs.append(
                        (original_holder_address, record.data.get("provider"))
                    )

                flagged_address_provider_pairs = set(flagged_address_provider_pairs)

                # Only want to slash addresses for stamps that are still valid
                addresses.extend(
                    CeramicCache.objects.filter(
                        (
                            {"address": p.address, "provider": p.provider}
                            for p in flagged_address_provider_pairs
                        ),
                        deleted_at=None,
                        stamp__expirationDate__gt=now,
                    )
                    .values_list("address", flat=True)
                    .distinct()
                )

                num_records = len(records)
                last_id = records[num_records - 1].pk
                progress_bar.update(num_records)

        return list(set(addresses))

    def create_slash_records(self, now: datetime, offender_addresses: List[str]):
        self.stdout.write(
            f"Finding stakes to slash for len(offender_addresses) addresses"
        )
        slash_batch = (
            SlashBatch.objects.filter(processed=False).order_by("-created_at").first()
        )

        if not slash_batch:
            slash_batch = SlashBatch.objects.create()

        with tqdm(
            unit="records", unit_scale=True, desc="Finding stakes to slash"
        ) as progress_bar:
            for i in range(0, len(offender_addresses), QUERY_BATCH_SIZE):
                addresses = offender_addresses[i : i + QUERY_BATCH_SIZE]
                stakes_to_slash = self.get_stakes_to_slash(addresses)

                slashes = [
                    Slash(
                        created_at=now,
                        batch=slash_batch,
                        staker=stake.staker,
                        stakee=stake.stakee,
                        offender=stake.offender,
                    )
                    for stake in stakes_to_slash
                ]

                progress_bar.update(len(addresses))

    def get_stakes_to_slash(self, offender_addresses: List[str]) -> List[StakeToSlash]:
        stakes_to_slash = []

        for address in offender_addresses:
            others_staked_on_by_address = []
            others_staking_on_this_address = []
            has_self_stake = False

            # TODO query indexer for stakes to populate above vars

            for stakee in others_staked_on_by_address:
                stakes_to_slash.append(
                    StakeToSlash(address, stakee, Slash.OffenderChoices.STAKER)
                )

            for staker in others_staking_on_this_address:
                stakes_to_slash.append(
                    StakeToSlash(staker, address, Slash.OffenderChoices.STAKEE)
                )

            if has_self_stake:
                stakes_to_slash.append(
                    StakeToSlash(address, address, Slash.OffenderChoices.STAKER)
                )

        return stakes_to_slash
