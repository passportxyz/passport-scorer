import csv
import json
from urllib.parse import urlparse

from cgrants.management.commands.utils import batch_iterator, stream_object_from_s3_uri
from cgrants.models import RoundMapping, SquelchedAccounts
from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm


def get_squelch_data_from_json(json_data, round_number):
    return SquelchedAccounts(
        address=json_data["voter"],
        score_when_squelched=json_data["score"],
        sybil_signal=json_data["sybil_signal"],
        round_number=round_number,
    )


class Command(BaseCommand):
    help = (
        "This command will import votes and contribution amounts for the Allo protocol."
    )

    def import_squelched_users(self, squelched_users_uri, round_number):
        num_errors = 0
        stream = stream_object_from_s3_uri(squelched_users_uri, self.stdout, self.style)
        if stream:
            self.stdout.write(self.style.SUCCESS(f"Got stream, processing JSONL"))

            total_size = None

            # Process each line of the JSONL file with a progress bar
            with tqdm(
                total=total_size, unit="B", unit_scale=True, desc="Processing JSONL"
            ) as pbar:
                self.stdout.write(f"reading squelched users lines ...")
                chunk_size = 1000

                for dataset in batch_iterator(stream.iter_lines(), chunk_size):
                    squelched_accounts = []
                    for line in dataset:
                        try:
                            json_data = json.loads(line)
                            squelched_accounts.append(
                                get_squelch_data_from_json(json_data, round_number)
                            )
                        except json.JSONDecodeError as e:
                            self.stdout.write(
                                self.style.ERROR(f"Error parsing JSON line: '{line}'")
                            )
                            self.stdout.write(self.style.ERROR(f"Error: '{e}'"))
                            num_errors = num_errors + 1

                        # Update the progress bar with the number of bytes read
                        pbar.update(len(line))

                    SquelchedAccounts.objects.bulk_create(
                        squelched_accounts,
                        ignore_conflicts=True,
                    )

        if num_errors == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "JSONL loading status: All records loaded succefully!"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"JSONL loading status: {num_errors} records failed to parse"
                )
            )

    def import_round_data(self, round_data_uri):
        num_errors = 0
        stream = stream_object_from_s3_uri(round_data_uri, self.stdout, self.style)
        if stream:

            for line in stream.read().decode("utf-8").splitlines():
                round_data = line.split(",")
                if round_data[0].startswith("GG"):
                    # ['program', 'type', 'chain_name', 'chain_id', 'round_name', 'round_id', 'matching_pool', 'starting_time']
                    round_number = int(round_data[0].split("GG")[1])
                    round_eth_address = round_data[5]
                    RoundMapping.objects.update_or_create(
                        round_number=round_number,
                        round_eth_address=round_eth_address,
                    )

        else:
            self.stdout.write(self.style.ERROR(f"Empty file read from S3: {s3_uri}"))

        if num_errors == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "CSV loading status: All records loaded successfully!"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"CSV loading status: {num_errors} records failed to parse"
                )
            )

    def add_arguments(self, parser):
        parser.add_argument(
            "--squelched-users-input",
            required=True,
            help="""S3 uri for input file, for example 's3://your_bucket_name/your_folder_name/your_file_name.txt'.
            Input file must be in JSONL format (that is 1 JSON record per line).)""",
        )

        parser.add_argument(
            "--round-data-input",
            required=True,
            help="""S3 uri for input file, for example 's3://your_bucket_name/your_folder_name/your_file_name.txt'.
            Input file should include all rounds and labels in csv format""",
        )

        parser.add_argument(
            "--round-number",
            required=True,
            help="""Round number in which users were squelched""",
        )

    def handle(self, *args, **options):
        squelched_users_uri = options["squelched_users_input"]
        round_number = options["round_number"]
        self.stdout.write(
            f'Squelched User Input file "{squelched_users_uri}" and round number "{round_number}"'
        )
        self.import_squelched_users(squelched_users_uri, round_number)

        round_data_uri = options["round_data_input"]
        self.stdout.write(f'Round Data Input file "{squelched_users_uri}"')
        self.import_round_data(round_data_uri)
