from django.conf import settings

if settings.LOGGING_STRATEGY in ("structlog_json", "structlog_flatline"):
    from structlog import *
else:
    from logging import *
