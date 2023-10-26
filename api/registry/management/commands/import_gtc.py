import csv

from django.core.management.base import BaseCommand
from registry.models import GTCStakeEvents
from tqdm import tqdm


class Command(BaseCommand):
    help = "Import data from a CSV file to GTCStakeEvents model."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Path to the CSV input file")

    def handle(self, *args, **options):
        input_file = options["csv"]
        self.stdout.write(self.style.SUCCESS(f"Importing data from '{input_file}'"))

        # Get the total number of lines in the CSV for tqdm progress bar
        total_lines = sum(1 for _ in open(input_file))

        with open(input_file, "r", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)

            # Using tqdm to show progress
            for row in tqdm(reader, total=total_lines, desc="Importing"):
                s = GTCStakeEvents(
                    event_type=row["event_type"],
                    round_id=int(row["round_id"]),
                    staker=row["staker"],
                    address=row.get("address", ""),
                    amount=row["amount"],
                    staked=row["staked"].lower() == "true",
                    block_number=int(row["block_number"]),
                    tx_hash=row["tx_hash"],
                )
                s.save()

        self.stdout.write(self.style.SUCCESS(f"Import completed!"))
