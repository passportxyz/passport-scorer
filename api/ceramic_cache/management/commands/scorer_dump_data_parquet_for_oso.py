import os.path
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from django.db.models.functions import Lower
from registry.models import Score
from scorer.export_utils import export_data_for_model, upload_to_s3


def get_pa_schema():
    schema = pa.schema(
        [
            ("passport_address", pa.string()),
            ("last_score_timestamp", pa.timestamp("ms")),
            ("evidence_rawScore", pa.string()),
            ("evidence_threshold", pa.string()),
            (
                "provider_scores",
                pa.list_(
                    pa.struct(
                        [
                            pa.field("provider", pa.string()),
                            pa.field("score", pa.string()),
                        ]
                    )
                ),
            ),  # stamp_scores
        ]
    )
    return schema


@contextmanager
def writer_context_manager(model):
    table_name = model._meta.db_table
    output_file = f"{table_name}.parquet"
    schema = get_pa_schema()
    try:
        with pq.ParquetWriter(output_file, schema) as writer:

            class WriterWrappe:
                def __init__(self, writer):
                    self.writer = writer

                def write_batch(self, data):
                    # Transform the data to match the parquet structure
                    transformed_data = [
                        {
                            "passport_address": d["passport_address"],
                            "last_score_timestamp": d["last_score_timestamp"],
                            "evidence_rawScore": d["evidence"]["rawScore"],
                            "evidence_threshold": d["evidence"]["threshold"],
                            "provider_scores": [
                                {"provider": k, "score": str(v)}
                                for k, v in d["stamp_scores"].items()
                            ],
                        }
                        for d in data
                    ]

                    batch = pa.RecordBatch.from_pylist(transformed_data, schema=schema)
                    self.writer.write_batch(batch)

            yield WriterWrappe(writer)
    finally:
        pass


class Command(BaseCommand):
    help = "Export data from a django model to a parquet file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="""Size of record batches.
            If present, this will read the records in batches. The result list is ordered by pk (id), to get
            to the next batch we query by id__gt=last_id.
            """,
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Nominates a specific database to dump fixtures from. "
            'Defaults to the "default" database.',
        )
        parser.add_argument(
            "--s3-uri", type=str, help="The S3 URI target location for the files"
        )

    def handle(self, *args, **options):
        self.batch_size = options["batch_size"]
        self.database = options["database"]
        self.s3_uri = options["s3_uri"]

        # Get the bucket name and folder from the S3 uri
        parsed_uri = urlparse(self.s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")

        # Append a sub-folder to th epath that consists of the current date <YYYY-MM-DD>
        now = datetime.now(timezone.utc)
        daily_folder_name = now.isoformat().split("T")[0]
        s3_folder = os.path.join(s3_folder, daily_folder_name)

        self.stdout.write("EXPORT - START export data for Score")
        try:
            output_file = f"{Score._meta.db_table}.parquet"
            export_data_for_model(
                # We only want to export for the default scorer
                Score.objects.filter(
                    passport__community__id=settings.CERAMIC_CACHE_SCORER_ID
                )
                .select_related("passport")
                .annotate(  # This is basically just a trick to get the `address` form the related `passport` into the values() output ...
                    passport_address=Lower("passport__address")
                )
                .using(self.database),
                "id",
                self.batch_size,
                writer_context_manager,
                jsonfields_as_str=False,
            )

            self.stdout.write(
                self.style.SUCCESS(f"EXPORT - Data exported to '{output_file}'")
            )

            upload_to_s3(output_file, s3_folder, s3_bucket_name, {})

            self.stdout.write(
                self.style.SUCCESS(
                    f"EXPORT - Data uploaded to folder '{s3_folder}' in bucket '{s3_bucket_name}'"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"EXPORT - Error when exporting data '{e}'")
            )
            self.stdout.write(self.style.ERROR(traceback.format_exc()))

        self.stdout.write("EXPORT - END export data for Score")
