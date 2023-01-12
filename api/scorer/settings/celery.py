from .env import env

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
