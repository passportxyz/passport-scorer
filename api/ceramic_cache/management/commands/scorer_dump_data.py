import datetime
import json
import os
import traceback
from urllib.parse import urlparse

import boto3
from django.apps import apps
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.serializers.python import Serializer as PythonSerializer
from django.db import DEFAULT_DB_ALIAS
from tqdm import tqdm

from .base_cron_cmds import BaseCronJobCmd


class ProgressBar:
    def __init__(self, progress_output, object_count, *args, **kwargs):
        self.progress_bar = progress_output
        self.counter = 0
        self.object_count = object_count

    def update(self, n):
        if n - self.counter >= 1000:
            self.progress_bar.update(n - self.counter)
            self.counter = n


class Serializer(PythonSerializer):
    """Convert a queryset to JSON Lines."""

    internal_use_only = False
    progress_class = ProgressBar

    def __init__(self, *args, **kwargs):
        self.last_id = 0
        self.select_related = kwargs.pop("select_related")
        super().__init__(*args, **kwargs)

    def _init_options(self):
        self._current = None
        self.total_items_count = 0
        self.last_id = 0
        self.json_kwargs = self.options.copy()
        self.json_kwargs.pop("stream", None)
        self.json_kwargs.pop("fields", None)
        self.json_kwargs.pop("indent", None)
        self.json_kwargs["separators"] = (",", ": ")
        self.json_kwargs.setdefault("cls", DjangoJSONEncoder)
        self.json_kwargs.setdefault("ensure_ascii", False)

    def start_serialization(self):
        self._init_options()

    def end_object(self, obj):
        # self._current has the field data
        self._current["id"] = self._value_from_field(obj, obj._meta.pk)

        json.dump(self._current, self.stream, **self.json_kwargs)
        self.stream.write("\n")
        self.last_id = self._current["id"]
        self.total_items_count += 1

    def getvalue(self):
        # Grandparent super
        return super(PythonSerializer, self).getvalue()

    def handle_fk_field(self, obj, fk_field):
        if self.select_related and fk_field.name in self.select_related:
            related = getattr(obj, fk_field.name)
            if related:
                self._current_related = {}
                # Use the concrete parent class' _meta instead of the object's _meta
                # This is to avoid local_fields problems for proxy models. Refs #17717.
                concrete_model = related._meta.concrete_model
                # When using natural primary keys, retrieve the pk field of the
                # parent for multi-table inheritance child models. That field must
                # be serialized, otherwise deserialization isn't possible.
                if self.use_natural_primary_keys:
                    pk = concrete_model._meta.pk
                    pk_parent = (
                        pk if pk.remote_field and pk.remote_field.parent_link else None
                    )
                else:
                    pk_parent = None
                for field in concrete_model._meta.local_fields:
                    if field.serialize or field is pk_parent:
                        if field.remote_field is None:
                            if (
                                self.selected_fields is None
                                or field.attname in self.selected_fields
                            ):
                                self.handle_related_field(related, field)
                        else:
                            if (
                                self.selected_fields is None
                                or field.attname[:-3] in self.selected_fields
                            ):
                                self.handle_related_fk_field(related, field)
                for field in concrete_model._meta.local_many_to_many:
                    if field.serialize:
                        if (
                            self.selected_fields is None
                            or field.attname in self.selected_fields
                        ):
                            self.handle_related_m2m_field(related, field)
                self._current[fk_field.name] = self._current_related
            else:
                self._current[fk_field.name] = None
        else:
            # Call super for parent
            super().handle_fk_field(obj, fk_field)

    def handle_related_field(self, obj, field):
        self._current_related[field.name] = self._value_from_field(obj, field)

    def handle_related_fk_field(self, obj, field):
        if self.use_natural_foreign_keys and hasattr(
            field.remote_field.model, "natural_key"
        ):
            related = getattr(obj, field.name)
            if related:
                value = related.natural_key()
            else:
                value = None
        else:
            value = self._value_from_field(obj, field)
        self._current_related[field.name] = value

    def handle_related_m2m_field(self, obj, field):
        if field.remote_field.through._meta.auto_created:
            if self.use_natural_foreign_keys and hasattr(
                field.remote_field.model, "natural_key"
            ):

                def m2m_value(value):
                    return value.natural_key()

                def queryset_iterator(obj, field):
                    return getattr(obj, field.name).iterator()

            else:

                def m2m_value(value):
                    return self._value_from_field(value, value._meta.pk)

                def queryset_iterator(obj, field):
                    return (
                        getattr(obj, field.name).select_related().only("pk").iterator()
                    )

            m2m_iter = getattr(obj, "_prefetched_objects_cache", {}).get(
                field.name,
                queryset_iterator(obj, field),
            )
            self._current_related[field.name] = [
                m2m_value(related) for related in m2m_iter
            ]


def export_data(model_config, file, database, batch_size=None):
    select_related = (
        model_config["select_related"] if "select_related" in model_config else None
    )
    serializer = Serializer(select_related=select_related)
    model = apps.get_model(model_config["name"])

    with tqdm(
        unit="records",
        unit_scale=True,
        desc=f"Exporting records of {model_config['name']}",
    ) as progress_bar:
        if batch_size is None:
            queryset = model.objects.using(database).order_by("id")
            if select_related:
                queryset = queryset.select_related(*select_related)
            if "filter" in model_config:
                queryset = queryset.filter(**model_config["filter"])

            serializer.serialize(
                queryset.iterator(), progress_output=progress_bar, stream=file
            )
        else:
            has_more_records = True
            query_filter = model_config["filter"] if "filter" in model_config else {}
            while has_more_records:
                query_filter["id__gt"] = serializer.last_id

                queryset = (
                    model.objects.using(database)
                    .order_by("id")
                    .filter(**query_filter)[:batch_size]
                )
                if select_related:
                    queryset = queryset.select_related(*select_related)
                serializer.counter = 0
                serializer.serialize(
                    queryset.iterator(), progress_output=progress_bar, stream=file
                )

                has_more_records = serializer.last_id != 0


class Command(BaseCronJobCmd):
    help = """Dump data to JSONL files on S3 directly.

    Example configs:

        [{"name":"ceramic_cache.CeramicCache"},{"name":"registry.Stamp"},{"name":"registry.Event"},{"name":"registry.HashScorerLink"}]

        [{"name":"registry.Score","filter": {"community_id":335}, "select_related":["passport"], "extra-args": {"ACL":"public-read"}}]

        [{"name":"registry.Score","filename":"my_custom_file.json","filter": {"community_id":335}, "extra-args": {"ACL":"public-read"}}]

    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="""Size of record batches.
            If present, this will read the records in batches. The result list is ordered by pk (id), to get
            to the next batch we query by id__gt=last_id.
            """,
        )
        parser.add_argument(
            "--config",
            type=str,
            help="""Configure the datat to be dumped. This needs to be an array, with 1 object per dump:
                            {
                                "name": "<model name> - for example ceramic_cache.CeramicCache",
                                "filename": "custom filename for the export, otherwise the tablename will be used by default",
                                "filter": "<filter to apply to query - this dict will be passed into the `filter(...) query method`>,
                                "extra-args": "<extra args to the s3 upload. This can be used to set dump file permissions, see: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/upload_file.html>"
                                "select_related":["<array of releated field names that should be expanded and included in the dump">]
                            }
                            """,
        )
        parser.add_argument(
            "--s3-uri", type=str, help="The S3 URI target location for the files"
        )
        parser.add_argument(
            "--s3-endpoint",
            type=str,
            default="https://s3.us-west-2.amazonaws.com",
            help="The S3 endpoint",
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Nominates a specific database to dump fixtures from. "
            'Defaults to the "default" database.',
        )
        parser.add_argument(
            "--cloudfront_distribution_id",
            default="",
            help="The CloudFront distribution id to create invalidation for the uploaded files",
        )
        parser.add_argument(
            "--summary-extra-args",
            default="{}",
            help="Extra args to add to the summary file upload. This can be used to set S3 permissions, see: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/upload_file.html. Defaults to {}.",
        )
        parser.add_argument(
            "--s3-access-key",
            type=str,
            default="",
            help="The S3 access key for dedicated S3 download (like digital ocean)",
        )
        parser.add_argument(
            "--s3-secret-access-key",
            type=str,
            default="",
            help="The S3 secret access key for dedicated S3 download (like digital ocean)",
        )

    def handle_cron_job(self, *args, **options):
        self.stdout.write("Dumping DB data")
        self.stdout.write("Args: " + str(args))
        self.stdout.write("Options: " + str(options))

        batch_size = options["batch_size"]
        config = options["config"]
        configured_models = json.loads(config)
        s3_uri = options["s3_uri"]
        s3_endpoint = options["s3_endpoint"]
        s3_access_key = options["s3_access_key"]
        s3_secret_access_key = options["s3_secret_access_key"]
        database = options["database"]
        summary_extra_args = json.loads(options["summary_extra_args"])
        cloudfront_distribution_id = options["cloudfront_distribution_id"]
        self.stdout.write("-" * 40)
        self.stdout.write(f"batch_size          : {batch_size}")
        self.stdout.write(f"config              : {config}")
        self.stdout.write(f"s3_uri              : {s3_uri}")
        self.stdout.write(f"s3_endpoint         : {s3_endpoint}")
        self.stdout.write(f"database            : {database}")
        self.stdout.write(f"summary_extra_args  : {summary_extra_args}")
        self.stdout.write(f"cloudfront_distribution_id  : {cloudfront_distribution_id}")
        self.stdout.write("-" * 40)

        if s3_access_key and s3_secret_access_key:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_access_key,
                endpoint_url=s3_endpoint,
            )
        else:
            # Use default credentials
            s3 = boto3.client("s3", endpoint_url=s3_endpoint)

        # Parse the S3 URI to extract bucket and key
        parsed_uri = urlparse(s3_uri)
        s3_bucket_name = parsed_uri.netloc
        s3_folder = parsed_uri.path.strip("/")
        summary = []
        try:
            for model_config in configured_models:
                model_summary = {
                    "model_config": model_config,
                    "start_time": datetime.datetime.now().isoformat(),
                }
                summary.append(model_summary)

                model_name = model_config["name"]
                self.stdout.write("-" * 40)
                self.stdout.write(f"Processing model: {model_name}")

                model = apps.get_model(model_name)
                file_name = (
                    f"{model._meta.db_table}.jsonl"
                    if "filename" not in model_config
                    else model_config["filename"]
                )

                s3_key = f"{s3_folder}/{file_name}"

                # chunk_size = 1000

                try:
                    # Write serialized data to the file
                    self.stdout.write(f"Serializing to file: {file_name}")
                    with open(file_name, "w", encoding="utf-8") as file:
                        export_data(
                            model_config, file, batch_size=batch_size, database=database
                        )

                    model_summary["start_s3_upload"] = (
                        datetime.datetime.now().isoformat()
                    )
                    self.stdout.write(
                        f"Uploading to s3, bucket='{s3_bucket_name}', key='{s3_key}'"
                    )

                    # Upload to S3 bucket
                    s3.upload_file(
                        file_name,
                        s3_bucket_name,
                        s3_key,
                        ExtraArgs=model_config.get("extra-args", {}),
                    )
                    model_summary["finished_at"] = datetime.datetime.now().isoformat()
                    model_summary["s3_key"] = s3_key
                    model_summary["s3_bucket_name"] = s3_bucket_name

                    if cloudfront_distribution_id:
                        client = boto3.client("cloudfront")
                        paths_to_invalidate = [f"/{s3_key}"]
                        self.stdout.write(
                            f"Create invalidation for {paths_to_invalidate} in the cloufront distribution {cloudfront_distribution_id}"
                        )
                        response = client.create_invalidation(
                            DistributionId=cloudfront_distribution_id,
                            InvalidationBatch={
                                "Paths": {
                                    "Quantity": len(paths_to_invalidate),
                                    "Items": paths_to_invalidate,
                                },
                                "CallerReference": str(
                                    datetime.datetime.utcnow().timestamp()
                                ),  # Unique reference, using timestamp
                            },
                        )
                        # Verify the response
                        if response["ResponseMetadata"]["HTTPStatusCode"] == 201:
                            invalidation_id = response["Invalidation"]["Id"]
                            self.stdout.write(
                                f"Invalidation created successfully. Invalidation ID: {invalidation_id}\n"
                            )
                        else:
                            self.stdout.write(
                                f"Failed to create invalidation. HTTP Status Code: {response['ResponseMetadata']['HTTPStatusCode']}\n"
                            )

                    os.remove(file_name)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"ERROR: {e}"))
                    self.stderr.write(traceback.format_exc())
                finally:
                    self.stdout.write(self.style.SUCCESS("Finished data dump"))

            upload_summary_file = "export_summary.json"
            with open(upload_summary_file, "w", encoding="utf-8") as file:
                json.dump(summary, file)

            s3_key = f"{s3_folder}/{upload_summary_file}"

            s3.upload_file(
                upload_summary_file,
                s3_bucket_name,
                s3_key,
                ExtraArgs=summary_extra_args,
            )
            os.remove(upload_summary_file)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"ERROR: {e}"))
            self.stderr.write(traceback.format_exc())
        finally:
            self.stdout.write(self.style.SUCCESS("Finished dump all data"))
