# --- Python imports
import random
import hashlib
import string
import logging
from typing import cast, List

# --- Web3 & Eth
from siwe import SiweMessage

# --- Ninja
from ninja_jwt.schema import RefreshToken
from ninja_schema import Schema
from ninja_extra import NinjaExtraAPI, status
from ninja import Schema, ModelSchema
from ninja_extra.exceptions import APIException
from ninja_jwt.authentication import JWTAuth

# --- Models
from account.models import Account, AccountAPIKey
from django.contrib.auth import get_user_model
from django.http import HttpResponse

log = logging.getLogger(__name__)

api = NinjaExtraAPI()


class SiweVerifySubmit(Schema):
    message: dict
    signature: str


CHALLENGE_STATEMENT = "I authorize the passport scorer.\n\nnonce:"

# Returns a random username to be used in the challenge
def get_random_username():
    return "".join(random.choice(string.ascii_letters) for i in range(32))


# API endpoint for nonce
# TODO - give nonce an expiration time and store it to verify the user
@api.get("/nonce")
def nonce(request):
    return {
        "nonce": hashlib.sha256(
            str("".join(random.choice(string.ascii_letters) for i in range(32))).encode(
                "utf"
            )
        ).hexdigest()
    }


class TokenObtainPairOutSchema(Schema):
    refresh: str
    access: str
    # user: UserSchema


class UserSchema(Schema):
    first_name: str
    email: str


class MyTokenObtainPairOutSchema(Schema):
    refresh: str
    access: str
    user: UserSchema

class UnauthorizedException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = 'UnAuthorized'

class TooManyKeysException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = 'You have already created 5 API Keys'

class AccountApiSchema(ModelSchema):
    class Config:
        model = AccountAPIKey
        model_fields = ['id', 'name']

@api.post("/verify", response=TokenObtainPairOutSchema)
def submit_signed_challenge(request, payload: SiweVerifySubmit):

    payload.message["chain_id"] = payload.message["chainId"]
    payload.message["issued_at"] = payload.message["issuedAt"]
    message: SiweMessage = SiweMessage(payload.message)

    # TODO: wrap in try-catch
    is_valid_signature = message.verify(
        payload.signature
    )  # TODO: add more verification params

    message.json()
    address_lower = payload.message["address"]

    try:
        account = Account.objects.get(address=address_lower)
    except Account.DoesNotExist:
        user = get_user_model().objects.create_user(username=get_random_username())
        user.save()
        account = Account(address=address_lower, user=user)
        account.save()

    refresh = RefreshToken.for_user(account.user)
    refresh = cast(RefreshToken, refresh)

    return {"ok": True, "refresh": str(refresh), "access": str(refresh.access_token)}


class APIKeyName(Schema):
    name: str

@api.post("/api-key", auth=JWTAuth())
def create_api_key(request, payload: APIKeyName):
    try:
        account = Account.objects.get(pk=request.user.id)

        if AccountAPIKey.objects.filter(account=account).count() >= 5:
            raise TooManyKeysException()

        key_name = payload.name

        api_key, key = AccountAPIKey.objects.create_key(account=account, name=key_name)
    except Account.DoesNotExist:
        raise UnauthorizedException()

    return { "api_key": key }

@api.get("/api-key", auth=JWTAuth(), response=List[AccountApiSchema])
def get_api_keys(request):
    try:
        account = Account.objects.get(pk=request.user.id)
        api_keys = AccountAPIKey.objects.filter(account=account).all()
        
    except Account.DoesNotExist:
        raise UnauthorizedException()
    return api_keys

def health(request):
    return HttpResponse("Ok")
