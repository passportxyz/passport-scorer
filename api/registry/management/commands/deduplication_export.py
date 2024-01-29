import datetime
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlparse

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand
from registry.models import HashScorerLink
from tqdm import tqdm


def write_csv_row(file, row):
    line = (
        ",".join(['"{}"'.format(str(item).replace('"', '""')) for item in row]) + "\n"
    )
    file.write(line.encode("utf-8"))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--community-id", type=int, required=True, help="Scorer ID")
        parser.add_argument(
            "--output-file", type=str, required=True, help="Output file Name"
        )
        parser.add_argument("--s3-uri", type=str, required=True, help="Bucket Name")

    def handle(self, *args, **options):
        community_id = options["community_id"]
        output_file = options["output_file"]
        s3_uri = options["s3_uri"]

        self.stdout.write(f"Exporting Squelched Addresses for community {community_id}")
        current_time = datetime.datetime.now()
        batch_size = 1000

        # Prepare S3 details
        parsed_uri = urlparse(s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")
        s3_key = f"{s3_folder}/{output_file}"

        temp_csv = BytesIO()
        unique_addresses = []
        with tqdm(
            unit="records", unit_scale=True, desc="Exporting records"
        ) as progress_bar:
            last_id = 0
            addresses = []
            while True:
                # Fetch a batch of records
                records = HashScorerLink.objects.filter(
                    community_id=community_id,
                    expires_at__gt=current_time,
                    id__gt=last_id,
                ).order_by("id")[:batch_size]

                if not records:
                    break

                for record in records:
                    addresses.append(record.address)
                    last_id = record.id
                    unique_addresses = list(set(addresses))
                    progress_bar.update(1)

        for address in unique_addresses:
            write_csv_row(temp_csv, [address])

        temp_csv.seek(0)
        self.stdout.write(f"Writing file to s3: {s3_key}")
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
        )

        s3.upload_fileobj(
            temp_csv, s3_bucket_name, s3_key, ExtraArgs={"ContentType": "text/csv"}
        )

        temp_csv.close()
        self.stdout.write(f"Uploaded to s3, bucket='{s3_bucket_name}', key='{s3_key}'")
