# --- Deduplication Modules
from django_ratelimit.exceptions import Ratelimited
from ninja_extra import NinjaExtraAPI

from account.models import (
    Nonce,
)
from registry.api.schema import (
    ErrorMessageResponse,
    SigningMessageResponse,
)
from registry.api.utils import (
    ApiKey,
    check_rate_limit,
    track_apikey_usage,
)
from registry.utils import (
    get_signing_message,
)

api = NinjaExtraAPI(
    urls_namespace="v2",
    title="Passport API V2",
    description="Endpoints to retrieve Passport scores, Stamps, analysis, and metadata.",
)


@api.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return api.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )


@api.get(
    "/signing-message",
    auth=ApiKey(),
    response={
        200: SigningMessageResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve a signing message",
    description="""Use this API to get a message to sign and a nonce to use when submitting your passport for scoring.""",
)
@track_apikey_usage(track_response=False)
def signing_message(request) -> SigningMessageResponse:
    check_rate_limit(request)
    nonce = Nonce.create_nonce().nonce
    return SigningMessageResponse(
        message=get_signing_message(nonce),
        nonce=nonce,
    )


from .api_models import *
from .api_stamps import *
