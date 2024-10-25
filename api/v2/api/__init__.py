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

from .api_models import *
from .api_stamps import *
from .router import api_router

api = NinjaExtraAPI(
    urls_namespace="v2",
    title="Passport API V2",
    description="Endpoints to retrieve Passport scores, Stamps, analysis, and metadata.",
)


api.add_router("", api_router)


@api.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return api.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )
