import json
from contextlib import contextmanager
from logging import getLogger
from google.cloud import storage

import boto3
import pyarrow as pa
import pyarrow.parquet as pq


from tqdm import tqdm

log = getLogger(__name__)


def get_pa_schema(model):
    schema = pa.schema(
        [
            # We need to take into consideration that for relation fields, we actually need the `fieldname + "_id"`
            (field.name, map_to_pa_schema_field(field.get_internal_type()))
            if not field.is_relation
            else (
                f"{field.name}_id",
                map_to_pa_schema_field(field.target_field.get_internal_type()),
            )
            for field in model._meta.fields
        ]
    )
    return schema


def map_to_pa_schema_field(django_internal_field_type):
    if django_internal_field_type in pa_schema_map:
        return pa_schema_map[django_internal_field_type]["pa_type"]

    log.warn(
        f"Unmapped django field type '{django_internal_field_type}'. Will default to `string`"
    )
    return pa.string()


def get_data(last_id, queryset, sort_field, batch_size):
    q = queryset.order_by(sort_field)

    if last_id:
        # Get only records after the last id / sort_field value
        q = q.filter(**{f"{sort_field}__gt": last_id})

    data = q[:batch_size].values()

    return list(data)


def get_data_json_as_str(last_id, queryset, sort_field, batch_size):
    """
    Same as `get_data` but serializes json fields (dict) to str
    """
    q = queryset.order_by(sort_field)

    if last_id:
        # Get only records after the last id / sort_field value
        q = q.filter(**{f"{sort_field}__gt": last_id})

    data = q[:batch_size].values()

    # In case of JSONField, the value will be a dict, which is not possible to serialize to Parquet
    # This is why we serialize that to JSON
    data = [
        {k: v if not isinstance(v, dict) else json.dumps(v) for k, v in d.items()}
        for d in data
    ]

    return data


def export_data_for_model(
    queryset, sort_field, batch_size, writer_context_manager, jsonfields_as_str=True
):
    data = (
        get_data_json_as_str(None, queryset, sort_field, batch_size)
        if jsonfields_as_str
        else get_data(None, queryset, sort_field, batch_size)
    )
    model = queryset.model
    # Define the output Parquet file
    table_name = model._meta.db_table

    # Export data for the model
    with tqdm(
        unit="records",
        unit_scale=True,
        desc=f"Exporting records of {table_name}",
    ) as progress_bar:
        if data is not None:
            progress_bar.update(len(data))
            with writer_context_manager(model) as writer:
                writer.write_batch(data)

                has_more = len(data) > 0

                while has_more:
                    last_id = data[-1][sort_field]
                    data = (
                        get_data_json_as_str(last_id, queryset, sort_field, batch_size)
                        if jsonfields_as_str
                        else get_data(last_id, queryset, sort_field, batch_size)
                    )

                    if data:
                        progress_bar.update(len(data))
                        has_more = True
                        last_id = data[-1][sort_field]

                        # Write the Pandas DataFrame to a Parquet file
                        writer.write_batch(data)
                    else:
                        has_more = False


def upload_to_s3(
    output_file,
    s3_folder,
    s3_bucket_name,
    extra_args,
):
    s3 = boto3.client("s3")

    s3_key = f"{s3_folder}/{output_file}"

    # Upload to S3 bucket
    s3.upload_file(
        output_file,
        s3_bucket_name,
        s3_key,
        ExtraArgs=extra_args,
    )


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


@contextmanager
def writer_context_manager(model):
    table_name = model._meta.db_table
    output_file = f"{table_name}.parquet"
    schema = get_pa_schema(model)
    try:
        with pq.ParquetWriter(output_file, schema) as writer:

            class WriterWrappe:
                def __init__(self, writer):
                    self.writer = writer

                def write_batch(self, data):
                    batch = pa.RecordBatch.from_pylist(data, schema=schema)
                    self.writer.write_batch(batch)

            yield WriterWrappe(writer)
    finally:
        pass


def upload_to_gcp(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    # Provide the path to the service account key
    storage_client = storage.Client.from_service_account_json(
        "path/to/your/service-account-key.json"
    )
    bucket = storage_client.bucket(bucket_name)

    # Note: Folders in GCP are created by adding a prefix to the file name
    blob = bucket.blob(destination_blob_name)

    # Upload the file
    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

    ## Example usage:
    # bucket_name = "your-bucket-name"
    # source_file_name = "local/path/to/your/file"
    # destination_blob_name = "new-folder/filename"  # 'new-folder/' is the folder

    # upload_to_gcp(bucket_name, source_file_name, destination_blob_name)
