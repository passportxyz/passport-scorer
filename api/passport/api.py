import json

import api_logging as logging
import requests
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


class EthereumModel(Schema):
    score: int


class NFTModel(Schema):
    score: int


class ZkSyncModel(Schema):
    score: int


class PassportAnalysisDetailsModels(Schema):
    ethereum: Optional[EthereumModel]
    nft: Optional[NFTModel]
    zksync: Optional[ZkSyncModel]


class PassportAnalysisDetails(Schema):
    models: PassportAnalysisDetailsModels


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
def get_analysis(request, address: str) -> PassportAnalysisResponse:
    return handle_get_analysis(address)


def handle_get_analysis(address: str) -> PassportAnalysisResponse:
    if not is_valid_address(address):
        raise InvalidAddressException()

    if len(models) > 1:
        raise BadModelNameError(
            detail="Currently, only one model name can be provided at a time"
        )

    if len(models) == 0 or models[0] == "":
        raise BadModelNameError(detail="No model names provided")

    bad_models = set(models) - set(MODEL_ENDPOINTS.keys())
    if bad_models:
        raise BadModelNameError(
            detail=f"Invalid model name(s): {', '.join(bad_models)}. Must be one of {', '.join(MODEL_ENDPOINTS.keys())}"
        )

    checksum_address = to_checksum_address(address)

    try:
        lambda_client = get_lambda_client()
        response = lambda_client.invoke(
            FunctionName="eth-stamp-v2-api",
            InvocationType="RequestResponse",
            Payload=json.dumps(
                {
                    "body": json.dumps({"address": checksum_address}),
                    "isBase64Encoded": False,
                }
            ),
        )

        decoded_response = response["Payload"].read().decode("utf-8")

        parsed_response = json.loads(decoded_response)

        response_body = json.loads(parsed_response["body"])

        score = response_body.get("data", {}).get("human_probability", 0)

        return PassportAnalysisResponse(
            address=address,
            details=PassportAnalysisDetails(
                models=PassportAnalysisDetailsModels(
                    ethereum_activity=EthereumActivityModel(score=score)
                )
            ),
        )

    except Exception:
        log.error("Error retrieving Passport analysis", exc_info=True)
        raise PassportAnalysisError()
