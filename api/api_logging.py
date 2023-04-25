from django.conf import settings

if settings.FF_USE_JSON_LOGGING == "on":
    from structlog import *
else:
    from logging import *
