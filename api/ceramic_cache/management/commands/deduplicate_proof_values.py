import csv
from django.core.management.base import BaseCommand
from ceramic_cache.models import (
    CeramicCache,
)


class Command(BaseCommand):
    help = "Deduplicate CeramicCache records based on proof_value, keeping the latest updated record"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file", type=str, help="Path to the CSV file containing proof_values"
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of proof_values to process in each batch",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        batch_size = options["batch_size"]

        total_processed = 0
        total_deleted = 0

        with open(csv_file, "r") as file:
            csv_reader = csv.reader(file)

            while True:
                # Read a batch of proof_values
                proof_values = [next(csv_reader)[0] for _ in range(batch_size)]
                proof_values = [
                    pv for pv in proof_values if pv
                ]  # Remove any empty values

                if not proof_values:
                    break  # End of file

                self.stdout.write(
                    f"Processing batch of {len(proof_values)} proof values..."
                )

                # Process each proof_value individually
                for proof_value in proof_values:
                    latest_record = (
                        CeramicCache.objects.filter(proof_value=proof_value)
                        .order_by("-updated_at")
                        .first()
                    )

                    if latest_record:
                        # Delete all other records for this proof_value
                        deleted_count = (
                            CeramicCache.objects.filter(proof_value=proof_value)
                            .exclude(id=latest_record.pk)
                            .delete()[0]
                        )

                        total_deleted += deleted_count

                    total_processed += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Processed {total_processed} proof values. Deleted {total_deleted} duplicate records so far."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Deduplication complete. Total processed: {total_processed}, Total deleted: {total_deleted}"
            )
        )
