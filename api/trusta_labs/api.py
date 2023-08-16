from django.conf import settings
from ninja import Schema
from ninja.security import APIKeyHeader
from ninja_extra import NinjaExtraAPI, status
from ninja_extra.exceptions import APIException
from registry.models import Event

api = NinjaExtraAPI(urls_namespace="trusta_labs")


class CgrantsApiKey(APIKeyHeader):
    param_name = "AUTHORIZATION"

    def authenticate(self, request, key):
        if key == settings.CGRANTS_API_TOKEN:
            return key


cg_api_key = CgrantsApiKey()


class TrustaLabsScorePayload(Schema):
    address: str
    score: int


class TrustaLabsScoreResponse(Schema):
    address: str
    score: int


class TrustaLabsScoreHasNoPayload(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "There is no payload with this request"


class TrustaLabsScoreHasNoAddress(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A Trusta Lab score must be accompanied by an address"


class TrustaLabsScoreHasNoScore(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A Trusta Lab request must include a score"


@api.post("/trusta-labs-score", auth=cg_api_key)
def create_trusta_labs_score_db(request, payload: TrustaLabsScorePayload):
    if payload == None:
        raise TrustaLabsScoreHasNoPayload()

    if payload.address == None:
        raise TrustaLabsScoreHasNoAddress()

    if payload.score == None:
        raise TrustaLabsScoreHasNoScore()

    Event.objects.create(
        action=Event.Action.TRUSTALAB_SCORE,
        address=payload.address.lower(),
        data={"score": payload.score},
    )
