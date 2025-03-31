from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from tqdm import tqdm

from registry.models import HashScorerLink, Stamp


class Command(BaseCommand):
    help = "Backfill stamps into hash link table"

    def add_arguments(self, parser):
        parser.add_argument(
            "--last-id", required=False, help="Starting ID, defaults to 0", default=0
        )
        parser.add_argument(
            "--iso-timestamp",
            required=False,
            help="Only include stamps expiring after and issued before this ISO timestamp (defaults to now)",
            default=datetime.now(timezone.utc).isoformat(),
        )

    def handle(self, *args, **options):
        last_id = options["last_id"]
        iso_timestamp = options["iso_timestamp"]
        self.stdout.write(self.style.SUCCESS(f'Starting ID "{last_id}"'))
        self.stdout.write(self.style.SUCCESS(f'ISO Timestamp "{iso_timestamp}"'))

        query = (
            Stamp.objects.filter(
                credential__expirationDate__gt=iso_timestamp,
                credential__issuanceDate__lt=iso_timestamp,
            )
            .select_related("passport")
            .order_by("id")
        )

        last_id = 0
        chunk_size = 1000

        try:
            with tqdm(
                unit="items", unit_scale=None, desc="Processing objects"
            ) as progress_bar:
                has_more = True
                while has_more:
                    objects = list(
                        query.filter(id__gt=last_id).using("read_replica_0")[
                            :chunk_size
                        ]
                    )
                    if objects:
                        last_id = objects[-1].id
                        hash_links = [
                            HashScorerLink(
                                hash=stamp.hash,
                                address=stamp.passport.address,
                                community=stamp.passport.community,
                                expires_at=stamp.credential["expirationDate"],
                            )
                            for stamp in objects
                        ]
                        HashScorerLink.objects.using("default").bulk_create(
                            hash_links, ignore_conflicts=True
                        )
                        progress_bar.update(len(objects))
                    else:
                        has_more = False

        finally:
            self.stdout.write(self.style.SUCCESS(f'Last ID "{last_id}"'))
