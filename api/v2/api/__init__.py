# --- Deduplication Modules
from django_ratelimit.exceptions import Ratelimited
from ninja_extra import NinjaExtraAPI

from ..exceptions import ScoreDoesNotExist
from .api_models import *
from .api_stamps import *
from .router import api_router

api = NinjaExtraAPI(
    urls_namespace="v2",
    title="Passport Developer Platform",
    description="The Passport Developer Platform's endpoints enable you to retrieve Passport scores, Stamps, analysis, and metadata.",
    version="2.0.0",
    docs_url="/v2/docs",
    openapi_url="/v2/openapi.json",
)


api.add_router("/v2", api_router)


@api.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return api.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )


@api.exception_handler(ScoreDoesNotExist)
def score_not_found(request, exc):
    return api.create_response(
        request,
        {"detail": exc.detail, "address": exc.address},
        status=exc.status_code
    )
