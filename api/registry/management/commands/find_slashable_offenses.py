from datetime import datetime, timedelta, timezone
from typing import List, Optional

from ceramic_cache.models import CeramicCache
from django.conf import settings
from django.core.management.base import BaseCommand
from registry.models import Event, HashScorerLink, SlashBatch
from tqdm import tqdm

QUERY_BATCH_SIZE = 1000


class Command(BaseCommand):
    def handle(self, *args, **options):
        offender_addresses = get_offender_addresses()

        create_slash_records(offender_addresses)

        self.stdout.write(f"TODO")


def get_offender_addresses() -> Optional[List[str]]:
    self.stdout.write(
        f"Finding Addresses involved in deduplication for community {dedup_community_id}"
    )

    now = datetime.now()
    now = now.replace(tzinfo=timezone.utc)
    three_months_ago = now - timedelta(days=90)

    dedup_community_id = settings.CERAMIC_CACHE_SCORER_ID

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
            addresses.append(
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


def create_slash_records(offender_addresses: List[str]):
    self.stdout.write(f"Finding stakes to slash for len(offender_addresses) addresses")
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

            progress_bar.update(len(addresses))
