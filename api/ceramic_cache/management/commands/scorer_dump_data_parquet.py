import json
import traceback
from pprint import pprint
from urllib.parse import urlparse

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from ceramic_cache.models import CeramicCache
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connection
from registry.models import Passport
from tqdm import tqdm

# The following mapping will map django field types to pyarrow types
pa_schema_map = {
    "AutoField": {"pa_type": pa.int64()},
    "BigAutoField": {"pa_type": pa.int64()},
    # "ForeignKey": {"pa_type": pa.int64()},
    # "OneToOneField": {"pa_type": pa.int64()},
    "CharField": {"pa_type": pa.string()},
    "JSONField": {"pa_type": pa.string(), "map_value": str},
    "DateTimeField": {"pa_type": pa.timestamp("ms")},
    "IntegerField": {"pa_type": pa.int64()},
    "BooleanField": {"pa_type": pa.bool_()},
    "DecimalField": {"pa_type": pa.decimal256(18, 9)},
}


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
            "--s3-uri", type=str, help="The S3 URI target location for the files"
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Nominates a specific database to dump fixtures from. "
            'Defaults to the "default" database.',
        )
        parser.add_argument(
            "--apps",
            type=str,
            help="""Comma separated list of app names for which to export data. We'll export all models for each app listed.""",
        )
        parser.add_argument(
            "--s3-extra-args",
            type=str,
            help="""JSON object, that contains extra args for the files uploaded to S3.
            This will be passed in as the `ExtraArgs` parameter to boto3's upload_file method.""",
        )

    def get_pa_schema(self, model):
        schema = pa.schema(
            [
                # We need to take into consideration that for relation fields, we actually need the `fieldname + "_id"`
                (field.name, self.map_to_pa_schema_field(field.get_internal_type()))
                if not field.is_relation
                else (
                    f"{field.name}_id",
                    self.map_to_pa_schema_field(field.target_field.get_internal_type()),
                )
                for field in model._meta.fields
            ]
        )
        print("SCHEMA:", schema)
        return schema

    def map_to_pa_schema_field(self, django_internal_field_type):
        if django_internal_field_type in pa_schema_map:
            return pa_schema_map[django_internal_field_type]["pa_type"]

        self.stdout.write(
            self.style.WARNING(
                f"Unmapped django field type '{django_internal_field_type}'. Will default to `string`"
            )
        )
        return pa.string()

    def get_data(self, model, last_id):
        q = model.objects.using(self.database).all().order_by("id")

        if last_id:
            q = q.filter(id__gt=last_id)

        data = q[: self.batch_size].values()

        # In case of JSONField, the value will be a dict, which is not possible to serialize to Parquet
        # This is why we serialize that to JSON
        data = [
            {k: v if type(v) is not dict else json.dumps(v) for k, v in d.items()}
            for d in data
        ]

        return (self.get_pa_schema(model), data)

    def export_data_for_model(self, model, s3_folder, s3_bucket_name, extra_args):
        schema, data = self.get_data(model, None)
        # Define the output Parquet file
        table_name = model._meta.db_table
        output_file = f"{table_name}.parquet"

        # Export data for the model
        with tqdm(
            unit="records",
            unit_scale=True,
            desc=f"Exporting records of {table_name}",
        ) as progress_bar:
            if data:
                progress_bar.update(len(data))
                with pq.ParquetWriter(output_file, schema) as writer:
                    batch = pa.RecordBatch.from_pylist(data, schema=schema)
                    writer.write_batch(batch)

                    has_more = True
                    last_id = data[-1]["id"]

                    while has_more:
                        _, data = self.get_data(model, last_id)

                        if data:
                            progress_bar.update(len(data))
                            has_more = False
                            last_id = data[-1]["id"]

                            # Write the Pandas DataFrame to a Parquet file
                            batch = pa.RecordBatch.from_pylist(data, schema=schema)
                            writer.write_batch(batch)
                        else:
                            has_more = False

                self.stdout.write(
                    self.style.SUCCESS(f"EXPORT - Data exported to '{output_file}'")
                )

                s3_key = f"{s3_folder}/{output_file}"

                # Upload to S3 bucket
                self.s3.upload_file(
                    output_file,
                    s3_bucket_name,
                    s3_key,
                    ExtraArgs=extra_args,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"EXPORT - Data uploaded to '{s3_bucket_name}/{s3_key}'"
                    )
                )

    def handle(self, *args, **options):
        last_id = 0
        has_more = True

        self.batch_size = options["batch_size"]
        self.s3_uri = options["s3_uri"]
        self.database = options["database"]
        apps_to_export = options["apps"].split(",") if options["apps"] else None
        extra_args = (
            json.parse(options["s3_extra_args"]) if options["s3_extra_args"] else None
        )

        self.stdout.write(f"EXPORT - s3_uri      : '{self.s3_uri}'")
        self.stdout.write(f"EXPORT - batch_size  : '{self.batch_size}'")
        self.stdout.write(f"EXPORT - database    : '{self.database}'")
        self.stdout.write(f"EXPORT - apps        : '{apps_to_export}'")

        if not apps:
            return

        parsed_uri = urlparse(self.s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
        )

        for app_name in apps_to_export:
            self.stdout.write(f"EXPORT - START export data for app: '{app_name}'")
            # Get the app's configuration
            app_config = apps.get_app_config(app_name)

            for model in app_config.get_models():
                self.stdout.write(
                    f"EXPORT - START export data for model: '{app_name}.{model._meta.model_name}'"
                )
                try:
                    self.export_data_for_model(
                        model,
                        s3_folder,
                        s3_bucket_name,
                        extra_args,
                    )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"EXPORT - Error when exporting data '{e}'")
                    )
                    self.stdout.write(self.style.ERROR(traceback.format_exc()))

                self.stdout.write(
                    f"EXPORT - END export data for model: '{app_name}.{model._meta.model_name}'"
                )

            self.stdout.write(f"EXPORT - END export data for app: '{app_name}'")
