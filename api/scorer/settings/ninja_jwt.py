from datetime import timedelta

from .env import env

NINJA_JWT = {
    "REFRESH_TOKEN_LIFETIME": env.timedelta(
        minutes=env.int("SCORER_UI_REFRESH_TOKEN_LIFETIME", default=1440)
    ),
}
