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

    try:
        # needs API auth and rate limiting
        from account.models import AccountAPIKey

        print("AccountAPIKey is loaded")

        headers = event["headers"]
        key = headers["x-api-key"]
        api_key = AccountAPIKey.objects.get_from_key(key)
        print("\nApi Key:", api_key)

        payload = json.loads(event["body"])
        print("\nBody:")
        pprint(payload)

        ret = handle_submit_passport(SubmitPassportPayload(**payload), api_key.account)
        print("\nData to return:", ret)
        return {
            "statusCode": 200,
            "statusDescription": "200 OK",
            "isBase64Encoded": False,
            "headers": {"Content-Type": "application/json"},
            "body": ret.json(),
        }

    except Exception as e:
        print(f"{'!':!>40}")
        print(e)
        print(f"{'!':!>40}")

    return {
        "statusCode": 200,
        "statusDescription": "200 OK",
        "isBase64Encoded": False,
        "headers": {"Content-Type": "text/html"},
        "body": "<h1>Hello from Lambda!</h1>",
    }
