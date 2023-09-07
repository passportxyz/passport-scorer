import base64
import json
from datetime import datetime, timezone
from functools import wraps
from typing import Tuple
from urllib.parse import unquote, urlencode

import api_logging as logging
import didkit
from django.conf import settings
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse_lazy
from eth_account.messages import encode_defunct
from registry.exceptions import NoRequiredPermissionsException
from registry.models import Stamp
from web3 import Web3

log = logging.getLogger(__name__)

web3 = Web3()


def index(request):
    context = {}
    return render(request, "registry/index.html", context)


async def validate_credential(did, credential):
    # pylint: disable=fixme
    stamp_return_errors = []
    credential_subject = credential.get("credentialSubject")
    stamp_hash = credential_subject.get("hash")
    stamp_did = credential_subject.get("id").lower()
    provider = credential_subject.get("provider")

    if not credential:
        stamp_return_errors.append("Missing or invalid attribute: credential")

    if not credential_subject:
        stamp_return_errors.append("Missing attribute: credentialSubject")

    if not stamp_hash:
        stamp_return_errors.append("Missing attribute: hash")

    if not stamp_did:
        stamp_return_errors.append("Missing attribute: id")

    if not provider:
        stamp_return_errors.append("Missing attribute: provider")

    if did != stamp_did:
        stamp_return_errors.append("Did mismatch")

    # pylint: disable=no-member
    verification = await didkit.verify_credential(
        json.dumps(credential), '{"proofPurpose":"assertionMethod"}'
    )
    verification = json.loads(verification)

    if verification["errors"]:
        stamp_return_errors.append(f"Stamp validation failed: {verification['errors']}")

    return stamp_return_errors


def get_duplicate_passport(did, stamp_hash):
    stamps = Stamp.objects.filter(hash=stamp_hash).exclude(passport__did=did)
    if stamps.exists():
        log.debug(
            "Duplicate did '%s' for stamp '%s'", stamps[0].passport.did, stamp_hash
        )
        return stamps[0].passport

    return None


def get_signing_message(nonce: str) -> str:
    return f"""I hereby agree to submit my address in order to score my associated Gitcoin Passport from Ceramic.

Nonce: {nonce}
"""


def get_signer(nonce: str, signature: str) -> str:
    message = get_signing_message(nonce)
    encoded_message = encode_defunct(text=message)
    address = web3.eth.account.recover_message(encoded_message, signature=signature)
    return address


def verify_issuer(stamp: dict) -> bool:
    return (
        "credential" in stamp
        and "issuer" in stamp["credential"]
        and stamp["credential"]["issuer"] == settings.TRUSTED_IAM_ISSUER
    )


def verify_expiration(passport) -> bool:
    format = "%Y-%m-%dT%H:%M:%S.%fZ"
    stamps = passport["stamps"]
    for index in stamps:
        if (
            datetime.strptime(index["credential"]["expirationDate"], format)
            < datetime.now()
        ):
            return False
    return True


def reverse_lazy_with_query(
    view, urlconf=None, args=None, kwargs=None, current_app=None, query_kwargs=None
):
    """Custom lazy reverse to handle query strings.
    Usage:
        reverse_lazy('app.views.my_view', kwargs={'pk': 123}, query_kwargs={'search': 'Bob'})
    """
    base_url = reverse_lazy(
        view, urlconf=urlconf, args=args, kwargs=kwargs, current_app=current_app
    )
    if query_kwargs:
        return "{}?{}".format(base_url, urlencode(query_kwargs))
    return str(base_url)


def permissions_required(permission_classes):
    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            for permission_class in permission_classes:
                permission = permission_class()
                if not permission.has_permission(request, None):
                    raise NoRequiredPermissionsException()
            return func(request, *args, **kwargs)

        return wrapped

    return decorator


def encode_cursor(**kwargs) -> str:
    encoded_bytes = base64.urlsafe_b64encode(json.dumps(dict(**kwargs)).encode("utf-8"))
    return encoded_bytes


def decode_cursor(token: str) -> dict:
    if token:
        return json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))
    return {}


def get_utc_time():
    return datetime.now(timezone.utc)


def get_cursor_query_condition(cursor):
    """
    This function will decode a cursor and return a query condition and ordering condition
    The implementation is specific to the requirements in  "/score/{int:scorer_id}" but it could be made
    more generic if required, and pass in the required:
    - sort_fields
    - filter_fields

    in order to be able to return the filer and order conditions
    """
    if cursor["d"] == "next":
        filter_condition = Q(
            last_score_timestamp__gt=cursor["last_score_timestamp"]
        ) | (
            Q(last_score_timestamp__gte=cursor["last_score_timestamp"])
            & Q(id__gt=cursor["id"])
        )

        if "address" in cursor and cursor["address"]:
            filter_condition &= Q(passport__address=cursor["address"])

        if "last_score_timestamp__gt" in cursor and cursor["last_score_timestamp__gt"]:
            filter_condition &= Q(
                last_score_timestamp__gt=cursor["last_score_timestamp__gt"]
            )

        if (
            "last_score_timestamp__gte" in cursor
            and cursor["last_score_timestamp__gte"]
        ):
            filter_condition &= Q(
                last_score_timestamp__gte=cursor["last_score_timestamp__gte"]
            )

        field_ordering = ["last_score_timestamp", "id"]
    else:
        filter_condition = Q(
            last_score_timestamp__lt=cursor["last_score_timestamp"]
        ) | (
            Q(last_score_timestamp__lte=cursor["last_score_timestamp"])
            & Q(id__gt=cursor["id"])
        )

        if "address" in cursor and cursor["address"]:
            filter_condition &= Q(passport__address=cursor["address"])

        if "last_score_timestamp__gt" in cursor and cursor["last_score_timestamp__gt"]:
            filter_condition &= Q(
                last_score_timestamp__gt=cursor["last_score_timestamp__gt"]
            )

        if (
            "last_score_timestamp__gte" in cursor
            and cursor["last_score_timestamp__gte"]
        ):
            filter_condition &= Q(
                last_score_timestamp__gte=cursor["last_score_timestamp__gte"]
            )
        field_ordering = ["-last_score_timestamp", "-id"]

    return (filter_condition, field_ordering)
