from .env import env

# These configuration settings will be used when accessing data
# on S3 URIs. This should typically be the case when importing or exporting
# data. Seet the `import_allo_votes` command for an example.
S3_DATA_AWS_SECRET_KEY_ID = env("S3_DATA_AWS_SECRET_KEY_ID", default=None)
S3_DATA_AWS_SECRET_ACCESS_KEY = env("S3_DATA_AWS_SECRET_ACCESS_KEY", default=None)
