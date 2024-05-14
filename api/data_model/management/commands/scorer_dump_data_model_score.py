import json
import traceback
from urllib.parse import urlparse


from django.core.management.base import BaseCommand
from scorer.export_utils import (
    export_data_for_model,
    upload_to_s3,
)
from data_model.models import Cache
from contextlib import contextmanager
from django.core.serializers.json import DjangoJSONEncoder
from logging import getLogger

log = getLogger(__name__)


def get_writer(output_file):
    @contextmanager
    def eth_stamp_writer_context_manager(queryset):
        try:
            with open(output_file, "w", encoding="utf-8") as file:

                class WriterWrappe:
                    def __init__(self, file):
                        self.file = file

                    def write_batch(self, data):
                        for d in data:
                            try:
                                value = d["value"]
                                address = d["key_1"].lower()
                                self.file.write(
                                    json.dumps(
                                        {
                                            "address": address,
                                            "data": {
                                                "score": str(
                                                    value["data"]["human_probability"]
                                                )
                                            },
                                            "updated_at": d["updated_at"],
                                        },
                                        cls=DjangoJSONEncoder,
                                    )
                                    + "\n"
                                )
                            except Exception:
                                log.error(
                                    f"Error when writing record '{d}'", exc_info=True
                                )

                yield WriterWrappe(file)
        finally:
            pass

    return eth_stamp_writer_context_manager


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
            "--data-model",
            type=str,
            help="""The name of the prediction data model for which to export data.

For example:
    - predict - for eth model v1
    - predict_eth_v2 - for eth model v1
    - predict_zksync - for zksync model
    - predict_zksync_v2 - for zksync model v2
""",
        )

        parser.add_argument("--filename", type=str, help="The output filename")

        parser.add_argument(
            "--s3-extra-args",
            type=str,
            help="""JSON object, that contains extra args for the files uploaded to S3.
            This will be passed in as the `ExtraArgs` parameter to boto3's upload_file method.""",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        s3_uri = options["s3_uri"]
        filename = options["filename"]
        data_model_name = options["data_model"]

        extra_args = (
            json.loads(options["s3_extra_args"]) if options["s3_extra_args"] else None
        )

        self.stdout.write(f"EXPORT - s3_uri      : '{s3_uri}'")
        self.stdout.write(f"EXPORT - batch_size  : '{batch_size}'")
        self.stdout.write(f"EXPORT - filename    : '{filename}'")

        parsed_uri = urlparse(s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")

        try:
            export_data_for_model(
                Cache.objects.filter(
                    key_0=data_model_name
                ),  # This will only filter the scores for eth_stamp_model (v1)
                "id",
                batch_size,
                get_writer(filename),
                jsonfields_as_str=False,
            )

            self.stdout.write(
                self.style.SUCCESS(f"EXPORT - Data exported to '{filename}'")
            )

            upload_to_s3(filename, s3_folder, s3_bucket_name, extra_args)

            self.stdout.write(
                self.style.SUCCESS(
                    f"EXPORT - Data uploaded to '{s3_bucket_name}/{s3_folder}/{filename}'"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"EXPORT - Error when exporting data '{e}'")
            )
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
