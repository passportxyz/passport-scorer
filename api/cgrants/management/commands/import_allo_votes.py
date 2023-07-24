import itertools
import json
from urllib.parse import urlparse

import boto3
from cgrants.models import ProtocolContributions
from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm


def iterate_array_in_chunks(arr, chunk_size):
    for i in range(0, len(arr), chunk_size):
        yield arr[i : i + chunk_size]


def batch_iterator(iterable, batch_size):
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, batch_size))
        if not batch:
            break
        yield batch


def get_prodocol_contribution_for_json(json_data):
    return ProtocolContributions(
        ext_id=json_data["id"],
        contributor=json_data["voter"],
        amount=json_data["amountUSD"],
        project=json_data["projectId"],
        round=json_data["roundId"],
        data=json_data,
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

    def stream_jsonl_from_s3_uri(self, s3_uri):
        # Parse the S3 URI to get the bucket name, folder, and file name
        parsed_uri = urlparse(s3_uri)
        bucket_name = parsed_uri.netloc
        path = parsed_uri.path.strip("/")
        folder_name, file_name = path.rsplit("/", 1)

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
        )

        try:
            response = s3.get_object(
                Bucket=bucket_name, Key=f"{folder_name}/{file_name}"
            )
            return response["Body"]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading file from S3: {e}"))
            return None

    def read_file_contents_from_s3_uri(self, s3_uri):
        # Parse the S3 URI to get the bucket name, folder, and file name
        parsed_uri = urlparse(s3_uri)
        bucket_name = parsed_uri.netloc
        path = parsed_uri.path.strip("/")
        folder_name, file_name = path.rsplit("/", 1)

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
        )

        try:
            response = s3.get_object(
                Bucket=bucket_name, Key=f"{folder_name}/{file_name}"
            )
            contents = response["Body"].read().decode("utf-8")
            return contents
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading file from S3: {e}"))
            return None

    def handle(self, *args, **options):
        s3_uri = options["in"]
        self.stdout.write(f'Input file "{s3_uri}"')
        num_errors = 0
        stream = self.stream_jsonl_from_s3_uri(s3_uri)
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
                            protocol_contributions.append(
                                get_prodocol_contribution_for_json(json_data)
                            )
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
