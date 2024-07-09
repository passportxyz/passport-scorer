import api_logging as logging
import requests
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
def get_analysis(request, address: str, model_list: str) -> PassportAnalysisResponse:
    return handle_get_analysis(address, model_list)


# TODO: this should be loaded from settings & env vars
MODEL_ENDPOINTS = {
    "ethereum": "http://core-alb.private.gitcoin.co/eth-stamp-v2-predict",
    "nft": "http://core-alb.private.gitcoin.co/nft-model-predict",
    "zksync": "http://core-alb.private.gitcoin.co/zksync-model-v2-predict",
}


def handle_get_analysis(address: str, model_list: str) -> PassportAnalysisResponse:
    models = [model.strip() for model in model_list.split(",")]

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
            detail=f"Invalid model name(s): {','.join(bad_models)}. Must be one of {','.join(MODEL_ENDPOINTS.keys())}"
        )

    checksum_address = to_checksum_address(address)

    try:
        response = requests.post(
            MODEL_ENDPOINTS[models[0]],
            json={"address": checksum_address},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        response.raise_for_status()

        response_body = response.json()

        print("Response body:", response_body)

        score = response_body.get("data", {}).get("human_probability", 0)

        # async def post(session, url, data):
        #     print("individual post request", url, data)
        #     headers = {"Content-Type": "application/json", "Accept": "application/json"}
        #     async with session.post(
        #         url, data=json.dumps(data), headers=headers
        #     ) as response:
        #         return await response.text()

        # async def fetch_all(requests):
        #     async with aiohttp.ClientSession() as session:
        #         tasks = []
        #         for url, data in requests:
        #             task = asyncio.ensure_future(post(session, url, data))
        #             tasks.append(task)
        #         responses = await asyncio.gather(*tasks)
        #         return responses

        # requests = []
        # for model_name in models:
        #     requests.append(
        #         (f"{MODEL_ENDPOINTS[model_name]}/", {"address": checksum_address})
        #     )

        # print("Requests:", requests)
        # # Run the event loop
        # responses = await fetch_all(requests)
        # print("Responses:", responses)

        # # Print the responses
        # for response in responses:
        #     print(response)

        return PassportAnalysisResponse(
            address=address,
            details=PassportAnalysisDetails(
                models=PassportAnalysisDetailsModels(
                    # TODO
                    ethereum_activity=EthereumActivityModel(score=score)
                )
            ),
        )

    except Exception:
        log.error("Error retrieving Passport analysis", exc_info=True)
        raise PassportAnalysisError()
