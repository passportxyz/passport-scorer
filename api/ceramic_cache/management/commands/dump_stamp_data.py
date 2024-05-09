import datetime
import json
import os

import boto3
from ceramic_cache.models import CeramicCache, StampExports
from django.conf import settings
from django.utils import timezone
from tqdm import tqdm
from .base_cron_cmds import BaseCronJobCmd

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
    aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
)


class Command(BaseCronJobCmd):
    help = "Weekly data dump of new Stamp data since the last dump."

    def handle_cron_job(self, *args, **options):
        print("Starting dump_stamp_data.py")

        latest_export = StampExports.objects.order_by("-last_export_ts").first()

        if not latest_export:
            print("No previous exports found. Exporting all data.")
            latest_export = StampExports(
                last_export_ts=datetime.date.fromisoformat("1970-01-01")
            )

        print(f"Getting Stamps updated since {latest_export.last_export_ts}")

        query = (
            CeramicCache.objects.values("stamp", "updated_at")
            .order_by("updated_at")
            .using("read_replica_0")
        )

        # Generate the dump file name
        file_name = f'stamps_{latest_export.last_export_ts.strftime("%Y%m%d_%H%M%S")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.jsonl'

        last_updated_at = latest_export.last_export_ts
        chunk_size = 1000

        try:
            # Write serialized data to the file
            with open(file_name, "w") as f:
                with tqdm(
                    unit="items", unit_scale=None, desc="Exporting stamps"
                ) as progress_bar:
                    has_more = True
                    while has_more:
                        objects = list(
                            query.filter(updated_at__gt=last_updated_at)[:chunk_size]
                        )
                        if objects:
                            num_objects = len(objects)
                            progress_bar.update(num_objects)

                            for cache_obj in objects:
                                f.write(
                                    json.dumps({"stamp": cache_obj["stamp"]}) + "\n"
                                )

                            last_updated_at = cache_obj["updated_at"]

                            # If we get less than the chunk size, we've reached the end
                            # No need to keep querying which could result in querying forever
                            if num_objects < chunk_size:
                                has_more = False
                        else:
                            has_more = False

        finally:
            self.stdout.write(
                self.style.SUCCESS(f'Last stamp updated at "{last_updated_at}"')
            )

        # Upload to S3 bucket
        s3.upload_file(file_name, settings.S3_WEEKLY_BACKUP_BUCKET_NAME, file_name)

        # Delete local file after upload
        os.remove(file_name)

        StampExports.objects.create(
            last_export_ts=last_updated_at, stamp_total=progress_bar.n
        )

        print(f"Data dump completed and uploaded to S3 as {file_name}")
