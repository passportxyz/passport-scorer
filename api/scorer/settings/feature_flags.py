"""Specify any feature flags here"""

from .env import env

# Human Points Program feature flag
HUMAN_POINTS_ENABLED = env.bool("HUMAN_POINTS_ENABLED", default=False)
