import asyncio
import json
from typing import List

import aiohttp
import api_logging as logging
import boto3
from django.conf import settings
from eth_utils.address import to_checksum_address
from ninja import Schema
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException
from registry.api.utils import ApiKey, is_valid_address
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


lambda_client = None


def get_lambda_client():
    global lambda_client
    if lambda_client is None:
        lambda_client = boto3.client(
            "lambda",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
            region_name="us-west-2",
        )
    return lambda_client


class EthereumActivityModel(Schema):
    score: int


class PassportAnalysisDetailsModels(Schema):
    ethereum_activity: EthereumActivityModel


class PassportAnalysisDetails(Schema):
    models: PassportAnalysisDetailsModels


class PassportAnalysisResponse(Schema):
    address: str
    details: PassportAnalysisDetails


class ErrorMessageResponse(Schema):
    detail: str


class PassportAnalysisError(APIException):
    status_code = 500
    default_detail = "Error retrieving Passport analysis"


@api.get(
    "/analysis/{address}",
    auth=ApiKey(),
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
    request, address: str, model_list: str = ""
) -> PassportAnalysisResponse:
    split_model_list = [model.trim for model in model_list.split(",")]
    return await handle_get_analysis(address, split_model_list)


# TODO: this should be loaded from settings & env vars
MODEL_ENDPOINTS = {
    "eth-model": "http://core-alb.private.gitcoin.co/eth-stamp-v2-predict",
    "nft-model": "http://core-alb.private.gitcoin.co/nft-model-predict",
    "zksync-model": "http://core-alb.private.gitcoin.co/zksync-model-v2-predict",
}


async def handle_get_analysis(
    address: str, model_list: List[str] = ["eth-model", "nft-model", "zksync-model"]
) -> PassportAnalysisResponse:
    if not is_valid_address(address):
        raise InvalidAddressException()

    checksum_address = to_checksum_address(address)

    try:

        async def post(session, url, data):
            headers = {"Content-Type": "application/json"}
            print("individual post request", url, data)
            async with session.post(
                url, data=json.dumps(data), headers=headers
            ) as response:
                return await response.text()

        async def fetch_all(requests):
            async with aiohttp.ClientSession() as session:
                tasks = []
                for url, data in requests:
                    task = asyncio.ensure_future(post(session, url, data))
                    tasks.append(task)
                responses = await asyncio.gather(*tasks)
                return responses

        requests = []
        for model_name in model_list:
            if model_name in MODEL_ENDPOINTS:
                requests.append(
                    (f"{MODEL_ENDPOINTS[model_name]}/", {"address": checksum_address})
                )
            else:
                # TODO: raise 400 cause bad model name
                pass

        print("Requests:", requests)
        # Run the event loop
        responses = await fetch_all(requests)
        print("Responses:", responses)

        # Print the responses
        for response in responses:
            print(response)

        return PassportAnalysisResponse(
            address=address,
            details=PassportAnalysisDetails(
                models=PassportAnalysisDetailsModels(
                    ethereum_activity=EthereumActivityModel(score=0)
                )
            ),
        )

    except Exception:
        log.error("Error retrieving Passport analysis", exc_info=True)
        raise PassportAnalysisError()
