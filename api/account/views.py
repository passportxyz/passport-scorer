# --- Python imports
import random
import hashlib
import string
import logging
from typing import cast

# --- Web3 & Eth
from web3.auto import w3
from siwe import SiweMessage

# --- Ninja
from ninja import NinjaAPI
from ninja_jwt.schema import RefreshToken
from ninja_schema import Schema
from ninja_extra import NinjaExtraAPI
from ninja import Schema

# --- Models
from .models import Account
from django.contrib.auth import get_user_model


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
