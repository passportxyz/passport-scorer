# --- Python imports
import random
import hashlib
import string
import logging
from typing import Dict, Optional, Type, cast

# --- Web3 & Eth
from eth_account.messages import defunct_hash_message
from web3.auto import w3
from siwe import SiweMessage

# --- Ninja
from ninja import NinjaAPI
from ninja_jwt.schema import TokenObtainPairSerializer, RefreshToken
from ninja_jwt.controller import TokenObtainPairController
from ninja_jwt.exceptions import AuthenticationFailed
from ninja_extra import api_controller, route
from ninja_schema import Schema
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_extra import NinjaExtraAPI
from ninja import Schema

# --- Models
from .models import Account
from django.contrib.auth import get_user_model

from pydantic import root_validator


log = logging.getLogger(__name__)

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)

class ChallengeSubmission(Schema):
    address: str
    signature: str

class SiweVerifySubmit(Schema):
    message: dict
    signature: str

CHALLENGE_STATEMENT = "I authorize the passport scorer.\n\nnonce:"

# Returns a random username to be used in the challenge
def get_random_username():
    return "".join(random.choice(string.ascii_letters) for i in range(32))

# API endpoint for challenge
@api.get("/challenge")
def challenge(request, address: str):
    challenge = {
        "statement": CHALLENGE_STATEMENT,
        "nonce": hashlib.sha256(
            str(
                address
                # + "".join(random.choice(string.ascii_letters) for i in range(32))  TODO: need to track the 'random' part
            ).encode("utf")
        ).hexdigest(),
    }
    return challenge

# API endpoint for nonce
@api.get("/nonce")
def nonce(request):
    return hashlib.sha256(
        str("".join(random.choice(string.ascii_letters) for i in range(32))).encode(
            "utf"
        )
    ).hexdigest()

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

    log.debug("payload %s", payload)
    
    payload.message["chain_id"] = payload.message["chainId"]
    payload.message["issued_at"] = payload.message["issuedAt"]
    message: SiweMessage = SiweMessage(payload.message)

    # TODO: wrap in try-catch
    is_valid_signature = message.verify(payload.signature)   # TODO: add more verification params

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

    return {"refresh": str(refresh), "access": str(refresh.access_token)}

    # TODO: return JWT token to the user
    # return {"ok": True}
