from datetime import datetime, timezone

from ceramic_cache.models import CeramicCache
from django.core.management.base import BaseCommand
from tqdm import tqdm


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--last-id",
            type=int,
            required=False,
            help="Last ID to start from",
            default=0,
        )
        parser.add_argument(
            "--output-file", type=str, required=True, help="Output file Name"
        )

    def handle(self, *args, **options):
        last_id = options["last_id"]
        output_file = options["output_file"]

        self.stdout.write(f"Exporting ETH stamps")
        now = datetime.now()
        now = now.replace(tzinfo=timezone.utc)
        batch_size = 1000

        # write to CSV file
        csv = open(output_file, "w")
        with tqdm(
            unit="stamps", unit_scale=True, desc="Dumping stamps"
        ) as progress_bar:
            while True:
                # Fetch a batch of records
                stamps = CeramicCache.objects.filter(
                    provider__in=[
                        "ETHEnthusiast",
                        "ETHMaxi",
                        "ETHPioneer",
                        "ETHAdvocate",
                    ],
                    id__gt=last_id,
                ).order_by("id")[:batch_size]

                if not stamps:
                    break

                num_records = len(stamps)
                last_id = stamps[num_records - 1].id
                progress_bar.update(num_records)

                for stamp in stamps:
                    csv.write(
                        f"{stamp.address},{stamp.provider},{stamp.updated_at},{value_for_stamp(stamp.provider)}\n"
                    )

        self.stdout.write(f"Last ID: {last_id}")

        csv.close()


def value_for_stamp(provider):
    if provider == "ETHEnthusiast":
        return 1
    if provider == "ETHPioneer":
        return 25
    if provider == "ETHAdvocate":
        return 50
    if provider == "ETHMaxi":
        return 75
