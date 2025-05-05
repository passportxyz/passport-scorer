import asyncio
import json
from typing import Dict, List, Optional, Tuple

import aiohttp
from django.conf import settings
from django_ratelimit.exceptions import Ratelimited
from eth_utils.address import to_checksum_address
from ninja import Schema
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException

import api_logging as logging
from registry.admin import get_s3_client
from registry.api.utils import (
    aapi_key,
    check_rate_limit,
    get_analysis_api_rate_limited_msg,
    is_valid_address,
)
from registry.exceptions import InvalidAddressException
from registry.models import BatchModelScoringRequest, BatchRequestStatus
from scorer.settings.model_config import MODEL_AGGREGATION_NAMES

log = logging.getLogger(__name__)

api = NinjaExtraAPI(
    urls_namespace="passport",
    title="Passport Analysis API",
    description="""
The Passport Analysis API provides a simple interface to retrieve Passport analytics.\n
This API requires an API key generated in the Scorer UI to be passed in the X-API-Key header.\n
Other endpoints documented at [/docs](/docs)
""",
)


class ScoreModel(Schema):
    score: float


class DetailedScoreModel(Schema):
    score: int
    num_transactions: Optional[int]
    first_funder: Optional[str]
    first_funder_amount: Optional[float]
    first_funder_timestamp: Optional[str]


@api.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return api.create_response(
        request,
        {"error": get_analysis_api_rate_limited_msg()},
        status=429,
    )


class PassportAnalysisDetails(Schema):
    models: Dict[str, ScoreModel | DetailedScoreModel]


class PassportAnalysisResponse(Schema):
    address: str
    details: PassportAnalysisDetails


class ErrorMessageResponse(Schema):
    detail: str


class BadModelNameError(APIException):
    status_code = 400
    default_detail = "Invalid model names"


class PassportAnalysisError(APIException):
    status_code = 500
    default_detail = "Error retrieving Passport analysis"


class DataScienceApiKey(APIKeyHeader):
    param_name = "AUTHORIZATION"

    def authenticate(self, request, key):
        if key == settings.DATA_SCIENCE_API_KEY:
            return key
        return None


data_science_auth = DataScienceApiKey()


class BatchResponse(Schema):
    created_at: str
    s3_url: Optional[str]
    status: BatchRequestStatus
    percentage_complete: int


@api.get(
    "/analysis/batch",
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
                        "Bucket": settings.BULK_SCORE_REQUESTS_BUCKET_NAME,
                        "Key": f"{settings.BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER}/{req.s3_filename}",
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


@api.get(
    "/analysis/{address}",
    auth=aapi_key,
    response={
        200: PassportAnalysisResponse,
        400: ErrorMessageResponse,
        500: ErrorMessageResponse,
    },
    summary="Retrieve Passport analysis for an Ethereum address",
    description="Retrieve Passport analysis for an Ethereum address, currently consisting of the ETH activity model humanity score (0-100, higher is more likely human).",
    tags=["Passport Analysis"],
)
async def get_analysis(
    request, address: str, model_list: str = None
) -> PassportAnalysisResponse:
    check_rate_limit(request)
    return await handle_get_analysis(address, model_list)


async def fetch(session, url, data):
    headers = {"Content-Type": "application/json"}
    try:
        async with session.post(
            url, data=json.dumps(data), headers=headers
        ) as response:
            body = await response.json()
            return {"status": response.status, "data": body.get("data")}
    except Exception as e:
        log.error(f"Error fetching {url}", exc_info=True)
        return {
            "status": 500,
            "data": {
                "human_probability": -1,
                "n_transactions": -1,
                "error": str(e),
            },
        }


async def fetch_all(urls, payload):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            task = asyncio.ensure_future(fetch(session, url, payload))
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses


async def handle_get_analysis(
    address: str,
    model_list: str = None,
    only_one_model=None,
    additional_data=False,
) -> PassportAnalysisResponse:
    only_one_model = (
        only_one_model if only_one_model is not None else settings.ONLY_ONE_MODEL
    )

    # Set default in case nothing was selected by the user
    if not model_list or model_list.strip() == "":
        model_list = settings.MODEL_ENDPOINTS_DEFAULT

    models = list(set([model.strip() for model in model_list.split(",")]))

    if not is_valid_address(address):
        raise InvalidAddressException()

    if only_one_model and len(models) > 1:
        raise BadModelNameError(
            detail="Currently, only one model name can be provided at a time"
        )

    if len(models) == 0 or models[0] == "":
        models = ""
        raise BadModelNameError(detail="No model names provided")

    bad_models = set(models) - set(settings.MODEL_ENDPOINTS.keys())
    if bad_models:
        raise BadModelNameError(
            detail=f"Invalid model name(s): {', '.join(bad_models)}. Must be one of {', '.join(settings.MODEL_ENDPOINTS.keys())}"
        )

    # The cache historically uses checksummed addresses, need to do this for consistency
    checksummed_address = to_checksum_address(address)

    try:
        non_aggregate_models = list(set(models) - {settings.AGGREGATE_MODEL_NAME})
        if non_aggregate_models:
            responses_data = await get_model_responses(
                non_aggregate_models, checksummed_address
            )
            model_responses = list(zip(non_aggregate_models, responses_data))
        else:
            model_responses = []

        model_responses_ok = all(
            response["status"] == 200 for _, response in model_responses
        )

        if model_responses_ok and settings.AGGREGATE_MODEL_NAME in models:
            aggregate_response = await get_aggregate_model_response(
                checksummed_address, model_responses
            )
            model_responses.append((settings.AGGREGATE_MODEL_NAME, aggregate_response))
            model_responses_ok = aggregate_response["status"] == 200

        if not model_responses_ok:
            details = [
                dict(model=model, status=response.get("status"))
                for model, response in model_responses
            ]
            raise PassportAnalysisError(
                f"Error retrieving Passport analysis: {json.dumps(details)}"
            )

        ret = PassportAnalysisResponse(
            address=address,
            details=PassportAnalysisDetails(models={}),
        )

        if additional_data:
            for model, response in model_responses:
                data = response.get("data", {})
                score = data.get("human_probability", 0)
                num_transactions = data.get("n_transactions", 0)
                first_funder = data.get("first_funder", "")
                first_funder_amount = data.get("first_funder_amount", 0)
                first_funder_timestamp = data.get("first_funder_timestamp", "")
                ret.details.models[model] = DetailedScoreModel(
                    score=score,
                    num_transactions=num_transactions,
                    first_funder=first_funder,
                    first_funder_amount=first_funder_amount,
                    first_funder_timestamp=first_funder_timestamp,
                )
        else:
            for model, response in model_responses:
                data = response.get("data", {})
                score = data.get("human_probability", 0)
                ret.details.models[model] = ScoreModel(score=score)

        return ret
    except PassportAnalysisError:
        raise
    except Exception as exc:
        log.error("Error retrieving Passport analysis", exc_info=True)
        raise PassportAnalysisError() from exc


async def get_aggregate_model_response(
    checksummed_address: str, prefetched_responses: List[Tuple[str, Dict]]
):
    model_responses = await get_submodel_responses_for_aggregate(
        checksummed_address, prefetched_responses
    )

    payload = {
        "address": checksummed_address,
        "data": {},
    }
    model_responses_ok = all(
        response["status"] == 200 for _, response in model_responses
    )

    if not model_responses_ok:
        # If querying at least one of the submodules resulted in an error, then throw an error
        details = [
            dict(model=model, status=response.get("status"))
            for model, response in model_responses
        ]

        raise PassportAnalysisError(
            f"Error retrieving Passport analysis: {json.dumps(details)}"
        )

    for model, response in model_responses:
        data = response.get("data", {})
        score = data.get("human_probability", 0)
        num_transactions = data.get("n_transactions", 0)
        model_key = MODEL_AGGREGATION_NAMES[model]

        payload["data"][f"score_{model_key}"] = score
        payload["data"][f"txs_{model_key}"] = num_transactions

    url = settings.MODEL_ENDPOINTS[settings.AGGREGATE_MODEL_NAME]

    return (await fetch_all([url], payload))[0]


async def get_submodel_responses_for_aggregate(
    checksummed_address: str, prefetched_responses: List[Tuple[str, Dict]]
):
    relevant_prefetched_responses = [
        (model, response)
        for model, response in prefetched_responses
        if model in MODEL_AGGREGATION_NAMES.keys()
    ]

    prefetched_models = [model for model, _ in relevant_prefetched_responses]

    additional_models = list(MODEL_AGGREGATION_NAMES.keys() - prefetched_models)

    additional_responses_data = await get_model_responses(
        additional_models, checksummed_address
    )

    additional_model_responses = list(zip(additional_models, additional_responses_data))

    return relevant_prefetched_responses + additional_model_responses


async def get_model_responses(models: List[str], checksummed_address: str):
    urls = [settings.MODEL_ENDPOINTS[model] for model in models]

    payload = {"address": checksummed_address}
    return await fetch_all(urls, payload)
