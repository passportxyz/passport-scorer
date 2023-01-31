""" Specify any feature flags here """
from .env import env

FEATURE_FLAG_DB_CACHE_API = env.bool("FEATURE_FLAG_DB_CACHE_API", default=False)
