import itertools
import json
from pprint import pprint
from urllib.parse import urlparse

import boto3
from ceramic_cache.models import CeramicCacheLegacy
from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm


def batch_iterator(iterable, batch_size):
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, batch_size))
        if not batch:
            break
        yield batch


class NotVerifiableCredential(Exception):
    pass


def get_ceramic_cache_legacy(json_data):
    if json_data:
        data_type = json_data.get("content", {}).get("type", [""])[0]
        controller = json_data.get("metadata", {}).get("controllers", [""])[0]
        address = controller.split(":")[-1]

        if data_type == "VerifiableCredential":
            provider = json_data["content"]["credentialSubject"]["provider"]

            return CeramicCacheLegacy(
                address=address,
                provider=provider,
                stamp=json_data["content"],
            )
        else:
            raise NotVerifiableCredential
    else:
        raise NotVerifiableCredential


class Command(BaseCommand):
    help = "This command will import ceramic cache legacy data into the DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--in",
            required=True,
            help="""S3 uri for input file, for example 's3://your_bucket_name/your_folder_name/your_file_name.txt'.
            Input file must be in JSONL format (that is 1 JSON record per line).)""",
        )

    def stream_object_from_s3_uri(self, s3_uri):
        # Parse the S3 URI to get the bucket name, folder, and file name
        parsed_uri = urlparse(s3_uri)
        bucket_name = parsed_uri.netloc
        path = parsed_uri.path.strip("/")

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
        )

        try:
            response = s3.get_object(Bucket=bucket_name, Key=path)
            return response["ContentLength"], response["Body"]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading file from S3: {e}"))
            return None

    def handle(self, *args, **options):
        s3_uri = options["in"]
        self.stdout.write(f'Input file "{s3_uri}"')
        num_errors = 0
        num_credentials = 0
        address_set = set()
        (total_size, stream) = self.stream_object_from_s3_uri(s3_uri)
        if stream:
            self.stdout.write(self.style.SUCCESS("Got stream, processing JSONL"))

            # Process each line of the JSONL file with a progress bar
            with tqdm(
                total=total_size, unit="B", unit_scale=True, desc="Processing JSONL"
            ) as pbar:
                chunk_size = 1000

                for dataset in batch_iterator(stream.iter_lines(), chunk_size):
                    ceramic_cache_objects = []
                    for line in dataset:
                        try:
                            json_data = json.loads(line)
                            record = get_ceramic_cache_legacy(json_data)
                            ceramic_cache_objects.append(record)
                            num_credentials = num_credentials + 1
                            address_set.add(record.address)
                        except json.JSONDecodeError as e:
                            self.stdout.write(
                                self.style.ERROR(f"Error loading credential: '{line}'")
                            )
                            self.stdout.write(self.style.ERROR(f"Error: '{e}'"))
                            num_errors = num_errors + 1
                        except NotVerifiableCredential:
                            pass
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f"Error loading credential: '{line}'")
                            )
                            self.stdout.write(self.style.ERROR(f"Error: '{e}'"))
                            num_errors = num_errors + 1

                        # Update the progress bar with the number of bytes read
                        pbar.update(len(line))

                    CeramicCacheLegacy.objects.bulk_create(
                        ceramic_cache_objects,
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
        self.stdout.write(
            self.style.SUCCESS(
                f"""Have imported in CeramicCacheLegacy:
                    - {num_credentials} verifiable credentials
                    - {len(address_set)} unique addresses
                    """
            )
        )
