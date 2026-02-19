import base64
import json
from datetime import datetime, timezone

import api_logging as logging

log = logging.getLogger(__name__)


def get_utc_time():
    return datetime.now(timezone.utc)


def pad_b64decoded_string(base64url_string):
    return base64url_string + "=" * (4 - len(base64url_string) % 4)


def pad_and_urlsafe_b64decode(base64url_string):
    return base64.urlsafe_b64decode(pad_b64decoded_string(base64url_string))


def base64url_to_json(base64url_string):
    # Decode the Base64 URL-encoded string
    decoded_bytes = pad_and_urlsafe_b64decode(base64url_string)

    # Convert the decoded bytes to a JSON object
    json_data = json.loads(decoded_bytes.decode("utf-8"))

    return json_data
