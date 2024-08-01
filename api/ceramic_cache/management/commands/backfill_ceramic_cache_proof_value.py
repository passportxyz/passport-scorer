import time

from django.core.management.base import BaseCommand
from django.db import connection

from ceramic_cache.models import CeramicCache


class Command(BaseCommand):
    help = "Backfills proof_value from JSON data"

    def handle(self, *args, **options):
        batch_size = 10000
        max_id = CeramicCache.objects.latest("id").id
        current_id = CeramicCache.objects.earliest("id").id

        while current_id <= max_id:
            self.stdout.write(
                self.style.NOTICE(f"Backfilling starting at id {current_id}")
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ceramic_cache_ceramiccache
                    SET
                        proof_value =  COALESCE(
                            (stamp::json->>'proof')::json->>'proofValue',
                            (stamp::json->>'proof')::json->>'jws',
                            'TEST'
                        )
                    WHERE
                        id >= %s
                        AND id < %s
                """,
                    [current_id, current_id + batch_size],
                )

            current_id += batch_size

            self.stdout.write(
                self.style.SUCCESS(f"Backfilled up to id {current_id - 1}")
            )

            time.sleep(5)

        self.stdout.write(self.style.SUCCESS("Data backfill completed successfully"))
