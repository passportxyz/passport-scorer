import datetime
import json
import os

import boto3
from ceramic_cache.models import CeramicCache, StampExports
from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from django.utils import timezone

s3 = boto3.resource("s3")
ecs = boto3.client("ecs")


class Command(BaseCommand):
    help = "Weekly data dump of new Stamp data since the last dump."

    def handle(self, *args, **options):
        print("Starting dump_stamp_data.py")

        latest_export = StampExports.objects.order_by("-last_export_ts").first()

        if not latest_export:
            print("No previous exports found. Exporting all data.")
            latest_export = StampExports.objects.create(
                last_export_ts=timezone.now() - datetime.timedelta(days=7)
            )

        # Retrieve all Stamp data since the last dump
        stamps = CeramicCache.objects.filter(
            created_at__gt=latest_export.last_export_ts
        ).values_list("stamp", flat=True)

        # Generate the dump file name
        file_name = f'stamps_{latest_export.last_export_ts.strftime("%Y%m%d_%H%M%S")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.jsonl'

        # Write serialized data to the file
        with open(file_name, "w") as f:
            for stamp in stamps:
                f.write(json.dumps({"stamp": stamp}) + "\n")

        # Upload to S3 bucket
        s3.Bucket(settings.AWS_BUCKET_NAME).upload_file(file_name, file_name)

        # Delete local file after upload
        os.remove(file_name)

        print(f"Data dump completed and uploaded to S3 as {file_name}")
