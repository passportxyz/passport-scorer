import api_logging as logging
from passport.api import (
    BatchResponse,
    ErrorMessageResponse,
    PassportAnalysisResponse,
    data_science_auth,
    handle_get_analysis,
)
from registry.admin import get_s3_client
from registry.api.utils import aapi_key, check_rate_limit
from registry.models import BatchModelScoringRequest, BatchRequestStatus
from scorer.settings import (
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_SCORE_REQUESTS_BUCKET_NAME,
)
from v2.api import api

log = logging.getLogger(__name__)


@api.get(
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
    request, address: str, model_list: str = ""
) -> PassportAnalysisResponse:
    check_rate_limit(request)
    return await handle_get_analysis(address, model_list)


# TODO Do we keep this here?
@api.get(
    "/models/analysis",
    auth=data_science_auth,
    response={
        200: list[BatchResponse],
        400: ErrorMessageResponse,
        500: ErrorMessageResponse,
    },
    summary="Retrieve batch scoring status and result",
    description="Retrieve batch scoring status and result",
    include_in_schema=False,
)
def get_batch_analysis_stats(request, limit: int = 10) -> list[BatchResponse]:
    requests = BatchModelScoringRequest.objects.order_by("-created_at")[:limit]
    return [
        BatchResponse(
            created_at=req.created_at.isoformat(),
            s3_url=(
                get_s3_client().generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": BULK_SCORE_REQUESTS_BUCKET_NAME,
                        "Key": f"{BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER}/{req.s3_filename}",
                    },
                    # 24 hrs
                    ExpiresIn=60 * 60 * 24,
                )
                if req.status == BatchRequestStatus.DONE
                else None
            ),
            status=req.status,
            percentage_complete=req.progress,
        )
        for req in requests
    ]
