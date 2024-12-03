from .env import env

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")

# If was not specified, we keep the default (Which will store on local)
if AWS_STORAGE_BUCKET_NAME:
    # See https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
