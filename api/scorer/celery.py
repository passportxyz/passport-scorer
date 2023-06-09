import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")

app = Celery("scorer")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

app.conf.task_routes = {
    "registry.tasks.score_registry_passport": {"queue": "score_registry_passport"},
    "registry.tasks.score_passport_passport": {"queue": "score_passport_passport"},
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
