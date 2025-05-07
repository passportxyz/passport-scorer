from .env import env

# These configuration settings will be used when accessing data
# on S3 URIs. This should typically be the case when importing or exporting
# data. Seet the `import_allo_votes` command for an example.
S3_WEEKLY_BACKUP_BUCKET_NAME = env("S3_WEEKLY_BACKUP_BUCKET_NAME", default=None)
