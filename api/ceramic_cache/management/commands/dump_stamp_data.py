import datetime
import json
import os

import boto3
from ceramic_cache.models import CeramicCache, StampExports
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.utils import timezone

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
    aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
)


class Command(BaseCommand):
    help = "Weekly data dump of new Stamp data since the last dump."

    def handle(self, *args, **options):
        print("Starting dump_stamp_data.py")

        latest_export = StampExports.objects.order_by("-last_export_ts").first()

        if not latest_export:
            queryset = CeramicCache.objects.all()
            print("Getting all Stamps")
        else:
            queryset = CeramicCache.objects.filter(
                created_at__gt=latest_export.last_export_ts
            )
            print(f"Getting Stamps since {latest_export.last_export_ts}")

        paginator = Paginator(
            queryset.values_list("stamp", flat=True),
            1000,
        )

        start = (
            latest_export.last_export_ts.strftime("%Y%m%d_%H%M%S")
            if latest_export
            else "beginng_of_stamp_creation"
        )

        # Generate the dump file name
        file_name = f'stamps_{start}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.jsonl'

        # Write serialized data to the file
        with open(file_name, "w") as f:
            for page in paginator.page_range:
                for stamp in paginator.page(page).object_list:
                    f.write(json.dumps({"stamp": stamp}) + "\n")

        # Upload to S3 bucket
        s3.upload_file(file_name, settings.S3_WEEKLY_BACKUP_BUCKET_NAME, file_name)

        # Delete local file after upload
        os.remove(file_name)

        StampExports.objects.create(
            last_export_ts=timezone.now(), stamp_total=paginator.count
        )

        print(f"Data dump completed and uploaded to S3 as {file_name}")
