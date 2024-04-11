import json
import traceback
from urllib.parse import urlparse


from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS
from scorer.export_utils import (
    export_data_for_model,
    upload_to_s3,
)
from data_model.models import Cache
from contextlib import contextmanager
from django.core.serializers.json import DjangoJSONEncoder
from logging import getLogger

log = getLogger(__name__)
output_file = "eth_model_scores.jsonl"


@contextmanager
def eth_stamp_writer_context_manager(queryset):
    try:
        with open(output_file, "w", encoding="utf-8") as file:

            class WriterWrappe:
                def __init__(self, file):
                    self.file = file

                def write_batch(self, data):
                    print("================================")
                    print(data)
                    for d in data:
                        try:
                            key = json.loads(d["key"])
                            address = key[1].lower()
                            print("address: ", address)
                            self.file.write(
                                json.dumps(
                                    {
                                        "address": address,
                                    },
                                    cls=DjangoJSONEncoder,
                                )
                                + "\n"
                            )
                        except Exception:
                            log.error(f"Error when writing record '{d}'", exc_info=True)

            yield WriterWrappe(file)
    finally:
        pass


class Command(BaseCommand):
    help = "Export eth-model score to jsonl"

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
            "--s3-uri", type=str, help="The S3 URI target location for the files"
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Nominates a specific database to dump fixtures from. "
            'Defaults to the "default" database.',
        )

        parser.add_argument(
            "--s3-extra-args",
            type=str,
            help="""JSON object, that contains extra args for the files uploaded to S3.
            This will be passed in as the `ExtraArgs` parameter to boto3's upload_file method.""",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        s3_uri = options["s3_uri"]
        database = options["database"]

        extra_args = (
            json.parse(options["s3_extra_args"]) if options["s3_extra_args"] else None
        )

        self.stdout.write(f"EXPORT - s3_uri      : '{s3_uri}'")
        self.stdout.write(f"EXPORT - batch_size  : '{batch_size}'")
        self.stdout.write(f"EXPORT - database    : '{database}'")

        parsed_uri = urlparse(s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")

        try:
            export_data_for_model(
                Cache.objects.all(),
                "key",
                batch_size,
                eth_stamp_writer_context_manager,
            )

            self.stdout.write(
                self.style.SUCCESS(f"EXPORT - Data exported to '{output_file}'")
            )

            upload_to_s3(output_file, s3_folder, s3_bucket_name, extra_args)

            self.stdout.write(
                self.style.SUCCESS(
                    f"EXPORT - Data uploaded to '{s3_bucket_name}/{s3_folder}/{output_file}'"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"EXPORT - Error when exporting data '{e}'")
            )
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
