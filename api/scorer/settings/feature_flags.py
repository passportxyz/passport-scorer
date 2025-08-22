"""Specify any feature flags here"""

from .env import env

# Human Points Program feature flag
HUMAN_POINTS_ENABLED = env.bool("HUMAN_POINTS_ENABLED", default=False)

# Human Points activation timestamp (Unix timestamp in seconds)
# Points will only be awarded for actions after this timestamp
HUMAN_POINTS_START_TIMESTAMP = env.int("HUMAN_POINTS_START_TIMESTAMP", default=0)

# MetaMask OG points feature flag
HUMAN_POINTS_MTA_ENABLED = env.bool("HUMAN_POINTS_MTA_ENABLED", default=False)
