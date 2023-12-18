import json
from urllib.parse import urlparse

import boto3
from cgrants.management.commands.utils import batch_iterator, stream_jsonl_from_s3_uri
from cgrants.models import SquelchedAccounts
from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm


def get_squelch_data_from_json(json_data):
    return SquelchedAccounts(
        address=json_data["voter"],
        score_when_squelched=json_data["score"],
        sybil_signal=json_data["sybil_signal"],
    )


class Command(BaseCommand):
    help = (
        "This command will import votes and contribution amounts for the Allo protocol."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--in",
            required=True,
            help="""S3 uri for input file, for example 's3://your_bucket_name/your_folder_name/your_file_name.txt'.
            Input file must be in JSONL format (that is 1 JSON record per line).)""",
        )

    def handle(self, *args, **options):
        s3_uri = options["in"]
        self.stdout.write(f'Input file "{s3_uri}"')
        num_errors = 0
        stream = stream_jsonl_from_s3_uri(s3_uri, self.stdout, self.style)
        if stream:
            self.stdout.write(self.style.SUCCESS(f"Got stream, processing JSONL"))

            total_size = None

            # Process each line of the JSONL file with a progress bar
            with tqdm(
                total=total_size, unit="B", unit_scale=True, desc="Processing JSONL"
            ) as pbar:
                self.stdout.write(f"reading lines ...")
                chunk_size = 1000

                for dataset in batch_iterator(stream.iter_lines(), chunk_size):
                    squelched_accounts = []
                    for line in dataset:
                        try:
                            json_data = json.loads(line)
                            squelched_accounts.append(
                                get_squelch_data_from_json(json_data)
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
        else:
            self.stdout.write(self.style.ERROR(f"Empty file read from S3: {s3_uri}"))

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
