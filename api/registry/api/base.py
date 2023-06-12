import logging

from account.models import Account, AccountAPIKey
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string
from django_ratelimit.core import is_ratelimited
from django_ratelimit.decorators import ALL
from django_ratelimit.exceptions import Ratelimited
from ninja.security import APIKeyHeader
from registry.tasks import asave_api_key_analytics, save_api_key_analytics

from ..exceptions import InvalidScorerIdException, Unauthorized
from .schema import SubmitPassportPayload

log = logging.getLogger(__name__)


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

            if settings.FF_API_ANALYTICS == "on":
                save_api_key_analytics(api_key.id, request.path)

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
    param_name = "HTTP_X_API_KEY"
    from pprint import pformat

    log.error("META %s", request)
    log.error("META %s", pformat(request.META))
    key = request.META.get(param_name)

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

    if settings.FF_API_ANALYTICS == "on":
        asave_api_key_analytics(api_key.id, request.path)

    user_account = await Account.objects.aget(pk=api_key.account_id)
    if user_account:
        request.user = await get_user_model().objects.aget(pk=user_account.user_id)
        return user_account

    raise Unauthorized()


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


# async def aget_scorer_id(payload: SubmitPassportPayload) -> str:
#     scorer_id = ""
#     if payload.scorer_id:
#         scorer_id = payload.scorer_id
#     elif payload.community and payload.community != "Deprecated":
#         scorer_id = payload.community
#     else:
#         raise InvalidScorerIdException()

#     return scorer_id
