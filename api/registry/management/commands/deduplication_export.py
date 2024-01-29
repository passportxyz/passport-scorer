from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urlparse

import boto3
from ceramic_cache.models import CeramicCache
from django.conf import settings
from django.core.management.base import BaseCommand
from registry.models import Event
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
        now = datetime.now()
        now = now.replace(tzinfo=timezone.utc)
        three_months_ago = now - timedelta(days=90)
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
                records = Event.objects.filter(
                    community_id=community_id,
                    id__gt=last_id,
                    action=Event.Action.LIFO_DEDUPLICATION,
                    # limit to the last 3 months assuming any record that may exist would be expired anyways
                    created_at__gt=three_months_ago,
                ).order_by("id")[:batch_size]

                if not records:
                    break

                flagged_addresses = set(record.address for record in records)
                flagged_providers = set(
                    record.data.get("provider") for record in records
                )
                flagged_address_provider_pairs = set(
                    (record.address, record.data.get("provider")) for record in records
                )

                # bulk retrieve all stamps for the flagged addresses and providers
                flagged_stamps = CeramicCache.objects.filter(
                    address__in=flagged_addresses,
                    provider__in=flagged_providers,
                    deleted_at=None,
                )

                for stamp in flagged_stamps:
                    if (
                        not stamp.address in unique_addresses
                        and (stamp.address, stamp.provider)
                        in flagged_address_provider_pairs
                    ):
                        unique_addresses.append(stamp.address)
                        write_csv_row(temp_csv, [stamp.address])

                last_id = records[len(records) - 1].id
                progress_bar.update(1)

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
