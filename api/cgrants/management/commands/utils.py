import itertools
from urllib.parse import urlparse

import boto3
from django.conf import settings


def iterate_array_in_chunks(arr, chunk_size):
    for i in range(0, len(arr), chunk_size):
        yield arr[i : i + chunk_size]


def batch_iterator(iterable, batch_size):
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, batch_size))
        if not batch:
            break
        yield batch


def stream_jsonl_from_s3_uri(s3_uri, stdout, style):
    # Parse the S3 URI to get the bucket name, folder, and file name
    parsed_uri = urlparse(s3_uri)
    bucket_name = parsed_uri.netloc
    path = parsed_uri.path.strip("/")

    folder_name, file_name = path.rsplit("/", 1)

    print(settings.S3_DATA_AWS_SECRET_KEY_ID, "settings.S3_DATA_AWS_SECRET_KEY_ID")
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
        aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
    )

    try:
        response = s3.get_object(Bucket=bucket_name, Key=f"{folder_name}/{file_name}")
        return response["Body"]
    except Exception as e:
        stdout.write(style.ERROR(f"Error reading file from S3: {e}"))
        return None
