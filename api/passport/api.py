import asyncio
import json
from typing import Dict

import aiohttp
import api_logging as logging
from django.conf import settings
from ninja import Schema
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException
from registry.api.utils import aapi_key, check_rate_limit, is_valid_address
from registry.exceptions import InvalidAddressException

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
    score: int


class PassportAnalysisDetails(Schema):
    models: Dict[str, ScoreModel]


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
    async with session.post(url, data=json.dumps(data), headers=headers) as response:
        return await response.json()


async def fetch_all(urls, address):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            task = asyncio.ensure_future(
                fetch(
                    session,
                    url,
                    {"address": address},
                )
            )
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses


async def handle_get_analysis(
    address: str, model_list: str = None
) -> PassportAnalysisResponse:
    # Set default in case nothing was selected by the user
    if not model_list or model_list.strip() == "":
        model_list = settings.MODEL_ENDPOINTS_DEFAULT

    models = [model.strip() for model in model_list.split(",")]

    if not is_valid_address(address):
        raise InvalidAddressException()

    if len(models) > 1:
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

    urls = [settings.MODEL_ENDPOINTS[model] for model in models]

    try:
        responses = await fetch_all(urls, address)

        ret = PassportAnalysisResponse(
            address=address,
            details=PassportAnalysisDetails(models={}),
        )
        for model, response in zip(models, responses):
            ret.details.models[model] = ScoreModel(
                score=response.get("data", {}).get("human_probability", 0)
            )

        return ret

    except Exception:
        log.error("Error retrieving Passport analysis", exc_info=True)
        raise PassportAnalysisError()
