import json

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
def get_analysis(request, address: str) -> PassportAnalysisResponse:
    return handle_get_analysis(address)


def handle_get_analysis(address: str) -> PassportAnalysisResponse:
    log.info("handle_get_analysis address={address}")
    if not is_valid_address(address):
        raise InvalidAddressException()

    checksum_address = to_checksum_address(address)
    log.info("handle_get_analysis checksum_address={checksum_address}")

    try:
        lambda_client = get_lambda_client()
        response = lambda_client.invoke(
            FunctionName="eth-stamp-api",
            InvocationType="RequestResponse",
            Payload=json.dumps(
                {
                    "body": json.dumps({"address": checksum_address}),
                    "isBase64Encoded": False,
                }
            ),
        )
        log.info("handle_get_analysis response={response}")
        log.info("handle_get_analysis type response={type(response)}")

        read_response = response["Payload"].read()
        log.info("handle_get_analysis type read_response={read_response}")

        decoded_response = read_response.decode("utf-8")
        log.info("handle_get_analysis type decoded_response={decoded_response}")

        parsed_response = json.loads(decoded_response)
        log.info("handle_get_analysis type parsed_response={parsed_response}")

        response_body = json.loads(parsed_response["body"])
        log.info("handle_get_analysis type response_body={response_body}")

        score = response_body.get("data", {}).get("human_probability", 0)
        log.info("handle_get_analysis type score={score}")

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
