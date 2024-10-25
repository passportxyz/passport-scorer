import api_logging as logging
from passport.api import (
    ErrorMessageResponse,
    PassportAnalysisResponse,
    handle_get_analysis,
)
from registry.api.utils import aapi_key, check_rate_limit

from .router import api_router

log = logging.getLogger(__name__)


@api_router.get(
    "/models/score/{address}",
    auth=aapi_key,
    response={
        200: PassportAnalysisResponse,
        400: ErrorMessageResponse,
        500: ErrorMessageResponse,
    },
    summary="Retrieve Passport analysis for an Ethereum address",
    description="Retrieve Passport analysis for an Ethereum address, currently consisting of the ETH activity model humanity score (0-100, higher is more likely human).",
    tags=["Model Analysis"],
)
async def get_analysis(
    request, address: str, model: str = ""
) -> PassportAnalysisResponse:
    check_rate_limit(request)
    return await handle_get_analysis(address, model)
