import json
import os
from pprint import pprint

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

import django
from django.conf import settings

# settings.configure(DEBUG=True)
django.setup()

if settings.configured:
    print(f"{'-':!>40}")
    print("Django is configured")
    print(f"{'-':!>40}")
else:
    print(f"{'!':!>40}")
    print("Django is NOT configured")
    print(f"{'!':!>40}")


from registry.api.v1 import SubmitPassportPayload, handle_submit_passport

# Now this script or any imported module can use any part of Django it needs.
# from myapp import models


def handler(event, _context):
    pprint(event)

    print("CWD: ", os.getcwd())
    print("DIR: ", os.listdir(os.getcwd()))
