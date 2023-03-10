"""Ninja JWT settings."""
from datetime import timedelta

from .env import env

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("SCORER_UI_ACCESS_TOKEN_LIFETIME", default=1440)
    ),
}
