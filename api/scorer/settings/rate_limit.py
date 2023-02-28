""" Specify any feature flags here """
from .env import env

RATELIMIT_FAIL_OPEN = True
RATELIMIT_ENABLE = env.bool("RATELIMIT_ENABLE", default=True)
