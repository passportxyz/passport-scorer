import functools

import api_logging as logging
from account.models import Account, AccountAPIKey
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string
from django_ratelimit.core import is_ratelimited
from django_ratelimit.decorators import ALL
from django_ratelimit.exceptions import Ratelimited
from ninja.compatibility.request import get_headers
from ninja.security import APIKeyHeader
from ninja.security.base import SecuritySchema
from registry.api.schema import SubmitPassportPayload
from registry.atasks import asave_api_key_analytics
from registry.exceptions import InvalidScorerIdException, Unauthorized
from registry.tasks import save_api_key_analytics

log = logging.getLogger(__name__)


def atrack_apikey_usage(track_response=True, payload_param_name=None):
    def decorator_track_apikey_usage(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):

            request = args[0]

            response = None
            error = None

            payload = kwargs.get(payload_param_name) if payload_param_name else None
            try:
                response = await func(*args, **kwargs)

            except Exception as e:
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

            try:
                response = func(*args, **kwargs)
            except Exception as e:
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
                )

            except Exception as e:
                log.exception("failed to store analytics")

            if error:
                raise error

            return response

        return wrapper

    return decorator_track_apikey_usage


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
                raise Unauthorized()

            try:
                key = auth_header.split()[1]
            except:
                raise Unauthorized()

        try:
            api_key = AccountAPIKey.objects.get_from_key(key)
            request.api_key = api_key
            user_account = api_key.account

            if user_account:
                request.user = user_account.user
                return user_account
        except AccountAPIKey.DoesNotExist:
            raise Unauthorized()


async def aapi_key(request):
    """
    The content of this function was copied form AccountAPIKey.objects.get_from_key and
    adjusted to our needs.
    We might want to fix the `AccountAPIKey.objects.aget_from_key` (the async version)
    """
    param_name = "X-API-Key"
    headers = get_headers(request)
    key = headers.get(param_name)

    if not key:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            raise Unauthorized()

        try:
            key = auth_header.split()[1]
        except:
            raise Unauthorized()

    if not key:
        raise Unauthorized()

    prefix, _, _ = key.partition(".")
    queryset = AccountAPIKey.objects.get_usable_keys()

    try:
        api_key = await queryset.aget(prefix=prefix)
        request.api_key = api_key
    except AccountAPIKey.DoesNotExist:
        raise Unauthorized()

    if not api_key.is_valid(key):
        raise Unauthorized()

    user_account = await Account.objects.aget(pk=api_key.account_id)
    if user_account:
        request.user = await get_user_model().objects.aget(pk=user_account.user_id)
        return user_account

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
    rate = request.api_key.rate_limit

    # Bypass rate limiting if rate is set to None
    if rate == "":
        return

    ratelimited = is_ratelimited(
        request=request,
        group="registry",
        fn=None,
        key=lambda _request, _group: request.api_key.prefix,
        rate=rate,
        method=ALL,
        increment=True,
    )
    request.limited = ratelimited or old_limited
    if ratelimited:
        cls = getattr(settings, "RATELIMIT_EXCEPTION_CLASS", Ratelimited)
        raise (import_string(cls) if isinstance(cls, str) else cls)()


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
