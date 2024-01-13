import itertools
import json
from urllib.parse import urlparse

from cgrants.management.commands.utils import batch_iterator, stream_object_from_s3_uri
from cgrants.models import ProtocolContributions
from django import contrib
from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm


class Command(BaseCommand):
    help = (
        "This command will import votes and contribution amounts for the Allo protocol."
    )

    def get_protocol_contribution_for_json(self, json_data):
        if ProtocolContributions.objects.filter(ext_id=json_data["id"]).exists():
            self.stdout.write(
                f"Skipping, contribution already exists {json_data['id']}"
            )
            return None
        return ProtocolContributions(
            ext_id=json_data["id"],
            contributor=json_data["voter"],
            amount=json_data["amountUSD"],
            project=json_data["projectId"],
            round=json_data["roundId"],
            data=json_data,
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

        stream = stream_object_from_s3_uri(s3_uri, self.stdout, self.style)
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
                    protocol_contributions = []
                    for line in dataset:
                        try:
                            json_data = json.loads(line)
                            contribution = self.get_protocol_contribution_for_json(
                                json_data
                            )
                            if contribution:
                                protocol_contributions.append(contribution)
                        except json.JSONDecodeError as e:
                            self.stdout.write(
                                self.style.ERROR(f"Error parsing JSON line: '{line}'")
                            )
                            self.stdout.write(self.style.ERROR(f"Error: '{e}'"))
                            num_errors = num_errors + 1

                        # Update the progress bar with the number of bytes read
                        pbar.update(len(line))

                    ProtocolContributions.objects.bulk_create(
                        protocol_contributions,
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
