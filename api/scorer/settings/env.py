import os
from pathlib import Path

import environ

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False),
    TEST_MNEMONIC=(
        str,
        "chief loud snack trend chief net field husband vote message decide replace",
    ),
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))
