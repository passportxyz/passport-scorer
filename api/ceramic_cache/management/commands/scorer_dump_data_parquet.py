import json
import traceback
from urllib.parse import urlparse

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS

from scorer.export_utils import (
    export_data_for_model,
    upload_to_s3,
    writer_context_manager,
)

from .base_cron_cmds import BaseCronJobCmd


class Command(BaseCronJobCmd):
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
        parser.add_argument(
            "--sort-field",
            type=str,
            help="""The field used to sort and batch the export. This is typically the id, but can be any unique field.""",
            default="id",
        )
        parser.add_argument(
            "--models",
            type=str,
            help="""Comma separated list of models to export. Can be specified as either 'app_name.model_name' or as table names.
            If specified, only these models will be exported.""",
        )

    def handle_cron_job(self, *args, **options):
        self.batch_size = options["batch_size"]
        self.s3_uri = options["s3_uri"]
        self.database = options["database"]
        self.sort_field = options["sort_field"]
        apps_to_export = options["apps"].split(",") if options["apps"] else None
        models_to_export = options["models"].split(",") if options["models"] else None
        extra_args = (
            json.loads(options["s3_extra_args"]) if options["s3_extra_args"] else None
        )

        self.stdout.write(f"EXPORT - s3_uri      : '{self.s3_uri}'")
        self.stdout.write(f"EXPORT - batch_size  : '{self.batch_size}'")
        self.stdout.write(f"EXPORT - database    : '{self.database}'")
        self.stdout.write(f"EXPORT - apps        : '{apps_to_export}'")
        self.stdout.write(f"EXPORT - models      : '{models_to_export}'")

        if not apps_to_export and not models_to_export:
            return

        parsed_uri = urlparse(self.s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")

        # If specific models are provided, organize them by app
        model_filter = {}
        if models_to_export:
            for model_spec in models_to_export:
                model_filter["__table_names__"] = model_filter.get(
                    "__table_names__", set()
                )
                model_filter["__table_names__"].add(model_spec)
        # Process each app
        for app_name in apps_to_export or {
            app for app in model_filter.keys() if app != "__table_names__"
        }:
            self.stdout.write(f"EXPORT - START export data for app: '{app_name}'")
            # Get the app's configuration
            try:
                app_config = apps.get_app_config(app_name)
            except LookupError:
                self.stdout.write(
                    self.style.WARNING(f"EXPORT - App '{app_name}' not found, skipping")
                )
                continue

            for model in app_config.get_models():
                model_name = model._meta.model_name
                table_name = model._meta.db_table

                # Skip if we have a model filter and this model isn't in it
                if models_to_export:
                    app_models = model_filter.get(app_name, set())
                    table_names = model_filter.get("__table_names__", set())
                    if not (model_name in app_models or table_name in table_names):
                        continue
                self.stdout.write(
                    f"EXPORT - START export data for model: '{app_name}.{model_name}'"
                )
                try:
                    output_file = f"{table_name}.parquet"
                    export_data_for_model(
                        model.objects.all().using(self.database),
                        self.sort_field,
                        self.batch_size,
                        writer_context_manager,
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

                self.stdout.write(
                    f"EXPORT - END export data for model: '{app_name}.{model._meta.model_name}'"
                )

            self.stdout.write(f"EXPORT - END export data for app: '{app_name}'")
