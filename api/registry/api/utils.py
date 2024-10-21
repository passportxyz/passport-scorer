import functools

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.utils.module_loading import import_string
from django_ratelimit.core import is_ratelimited
from django_ratelimit.decorators import ALL
from django_ratelimit.exceptions import Ratelimited
from eth_utils.address import (
    is_checksum_address,
    is_checksum_formatted_address,
    is_hex_address,
)
from ninja.security import APIKeyHeader
from ninja.security.base import SecuritySchema
from ninja_extra.exceptions import APIException

import api_logging as logging
from account.models import Account, AccountAPIKey, AccountAPIKeyAnalytics
from registry.api.schema import SubmitPassportPayload
from registry.atasks import asave_api_key_analytics
from registry.exceptions import InvalidScorerIdException, Unauthorized
from registry.tasks import save_api_key_analytics

log = logging.getLogger(__name__)

PASSPORT_API_RATE_LIMITING_FORM = settings.PASSPORT_API_RATE_LIMITING_FORM
MBD_API_RATE_LIMITING_FORM = settings.MBD_API_RATE_LIMITING_FORM


def get_passport_api_rate_limited_msg() -> str:
    return f"You have been rate limited! Use this form to request a rate limit elevation: {PASSPORT_API_RATE_LIMITING_FORM}"


def get_analysis_api_rate_limited_msg() -> str:
    return f"You have been rate limited! Use this form to request a rate limit elevation: {MBD_API_RATE_LIMITING_FORM}"


def atrack_apikey_usage(track_response=True, payload_param_name=None):
    def decorator_track_apikey_usage(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = args[0]

            response = None
            error = None
            status_code = 200

            payload = kwargs.get(payload_param_name) if payload_param_name else None

            try:
                response = await func(*args, **kwargs)
                if hasattr(response, "status_code"):
                    status_code = response.status_code
            except APIException as e:
                error = e
                status_code = e.status_code
            except Exception as e:
                if isinstance(e, Ratelimited):
                    status_code = 429
                    error = e
                else:
                    status_code = 500
                    error = e

            try:
                await asave_api_key_analytics(
                    request.api_key.id,
                    request.path,
                    request.path.split("/")[
                        1:
                    ],  # skip the first element, as it will be the empty string
                    dict(request.GET),
                    dict(request.headers),
                    payload.json() if payload else None,
                    response=response.json() if track_response and response else None,
                    response_skipped=not track_response,
                    error=str(error) if error else None,
                    status_code=status_code,
                )
            except Exception as e:
                log.exception("failed to store analytics")

            if error:
                raise error

            return response

        return wrapper

    return decorator_track_apikey_usage


def track_apikey_usage(track_response=True, payload_param_name=None):
    def decorator_track_apikey_usage(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = args[0]

            response = None
            error = None
            payload = kwargs.get(payload_param_name) if payload_param_name else None
            status_code = 200

            try:
                response = func(*args, **kwargs)
                if hasattr(response, "status_code"):
                    status_code = response.status_code
            except APIException as e:
                error = e
                status_code = e.status_code
            except Exception as e:
                if isinstance(e, Ratelimited):
                    status_code = 429
                    error = e
                else:
                    status_code = 500
                    error = e

            try:
                save_api_key_analytics(
                    request.api_key.id,
                    request.path,
                    request.path.split("/")[
                        1:
                    ],  # skip the first element, as it will be the empty string
                    dict(request.GET),
                    dict(request.headers),
                    payload.json() if payload else None,
                    response=response.json() if track_response and response else None,
                    response_skipped=not track_response,
                    error=str(error) if error else None,
                    status_code=status_code,
                )

            except Exception as e:
                log.exception("failed to store analytics")

            if error:
                raise error

            return response

        return wrapper

    return decorator_track_apikey_usage


def track_usage(request: HttpRequest, key: str, status_code: int) -> None:
    """
    Track API key usage regardless of authentication outcome
    """
    try:
        api_key = AccountAPIKey.objects.filter(prefix=key[:8]).first()

        AccountAPIKeyAnalytics.objects.create(
            api_key=api_key,
            path=request.path,
            method=request.method,
            status_code=status_code,
            api_key_id=api_key.id if api_key else None,
            error="Unauthorized request",
        )
    except Exception:
        pass


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        """
        The authenticate method will validate the API key:
        1. first in the X-API-Key header - this will have preceedence
        2. in the HTTP_AUTHORIZATION header if none exists in the X-API-Key header (this is for backwards compatibility)
        """
        if not key:
            # if X-API-Key was not specified in the header read the HTTP_AUTHORIZATION
            # and try to load the tey from there
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")

            if not auth_header:
                track_usage(request, "", 401)
                raise Unauthorized()

            try:
                key = auth_header.split()[1]
            except:
                track_usage(request, "", 401)
                raise Unauthorized()

        try:
            api_key = AccountAPIKey.objects.get_from_key(key)
            request.api_key = api_key
            user_account = api_key.account

            if user_account:
                request.user = user_account.user
                return user_account
        except AccountAPIKey.DoesNotExist:
            track_usage(request, "", 401)
            raise Unauthorized()


async def atrack_usage(request, key: str, status_code: int) -> None:
    """
    Async version of track_usage for recording API key analytics
    """
    try:
        prefix = key.partition(".")[0] if key else ""

        api_key = None
        if prefix:
            try:
                api_key = await AccountAPIKey.objects.filter(prefix=prefix).afirst()
            except Exception:
                pass

        await AccountAPIKeyAnalytics.objects.acreate(
            api_key=api_key,
            path=request.path,
            method=request.method,
            status_code=status_code,
            api_key_id=api_key.id if api_key else None,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
    except Exception as e:
        pass


async def aapi_key(request):
    """
    The content of this function was copied form AccountAPIKey.objects.get_from_key and
    adjusted to our needs.
    We might want to fix the `AccountAPIKey.objects.aget_from_key` (the async version)
    """
    param_name = "X-API-Key"
    headers = request.headers
    key = headers.get(param_name)

    if not key:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            await atrack_usage(request, "", 401)
            raise Unauthorized()

        try:
            key = auth_header.split()[1]
        except:
            await atrack_usage(request, "", 401)
            raise Unauthorized()

    if not key:
        await atrack_usage(request, "", 401)
        raise Unauthorized()

    prefix, _, _ = key.partition(".")
    queryset = AccountAPIKey.objects.get_usable_keys()

    try:
        api_key = await queryset.aget(prefix=prefix)
        request.api_key = api_key
    except AccountAPIKey.DoesNotExist:
        await atrack_usage(request, "", 401)
        raise Unauthorized()

    if not api_key.is_valid(key):
        await atrack_usage(request, "", 401)
        raise Unauthorized()

    user_account = await Account.objects.aget(pk=api_key.account_id)
    if user_account:
        request.user = await get_user_model().objects.aget(pk=user_account.user_id)
        return user_account

    await atrack_usage(request, "", 401)
    raise Unauthorized()


# Following information & settings on aapi_key are meant to enable
# the auth feature in the live docs
aapi_key.openapi_security_schema_name = "ApiKey"
aapi_key.openapi_security_schema: SecuritySchema = SecuritySchema(
    **{"in": "header", "name": "X-API-Key", "type": "apiKey"}
)


def check_rate_limit(request):
    """
    Check the rate limit for the API.
    This is based on the original ratelimit decorator from django_ratelimit
    """
    old_limited = getattr(request, "limited", False)

    if request.path.startswith("/passport/"):
        ratelimited = check_analysis_rate_limit(request)
    else:
        ratelimited = check_standard_rate_limit(request)

    request.limited = ratelimited or old_limited

    if ratelimited:
        cls = getattr(settings, "RATELIMIT_EXCEPTION_CLASS", Ratelimited)
        raise (import_string(cls) if isinstance(cls, str) else cls)()


def check_standard_rate_limit(request) -> bool:
    rate = request.api_key.rate_limit

    # Bypass rate limiting if rate is set to None
    if rate == "":
        return False

    return is_ratelimited(
        request=request,
        group="registry",
        fn=None,
        key=lambda _request, _group: request.api_key.prefix,
        rate=rate,
        method=ALL,
        increment=True,
    )


def check_analysis_rate_limit(request) -> bool:
    rate = request.api_key.analysis_rate_limit

    # Bypass rate limiting if rate is set to None
    if rate == "":
        return False

    return is_ratelimited(
        request=request,
        group="analysis",
        fn=None,
        key=lambda _request, _group: request.api_key.prefix,
        rate=rate,
        method=ALL,
        increment=True,
    )


# TODO define logic once Community model has been updated
def community_requires_signature(_):
    return False


def get_scorer_id(payload: SubmitPassportPayload) -> str:
    scorer_id = ""
    if payload.scorer_id:
        scorer_id = payload.scorer_id
    elif payload.community and payload.community != "Deprecated":
        scorer_id = payload.community
    else:
        raise InvalidScorerIdException()

    return scorer_id


def with_read_db(model):
    return model.objects.using(settings.REGISTRY_API_READ_DB)


def is_valid_address(address: str) -> bool:
    return (
        is_checksum_address(address)
        if is_checksum_formatted_address(address)
        else is_hex_address(address)
    )
