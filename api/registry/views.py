# --- Python imports
import random
import hashlib
import string
import json
import logging
from typing import cast, List
from django.shortcuts import get_object_or_404
from asgiref.sync import async_to_sync
from datetime import datetime, timedelta

# --- Ninja
from ninja_jwt.schema import RefreshToken
from ninja_schema import Schema
from ninja_extra import NinjaExtraAPI, status
from ninja import Schema, ModelSchema
from ninja_extra.exceptions import APIException
from ninja_jwt.authentication import JWTAuth
from ninja.security import APIKeyHeader

# --- Models
from account.models import Account, AccountAPIKey, Community
from registry.models import Passport, Stamp, Score
from django.contrib.auth import get_user_model
from django.http import HttpResponse

# --- Passport Utilities
from registry.utils import validate_credential, get_signer, verify_issuer
from reader.passport_reader import get_did, get_passport

from ninja.compatibility.request import get_headers

log = logging.getLogger(__name__)
api = NinjaExtraAPI(urls_namespace="registry")


class InvalidSignerException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Address does not match signature."


class InvalidPassportCreationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Error Creating Passport."


class Unauthorized(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid API Key."


class SubmitPassportPayload(Schema):
    address: str
    signature: str
    community: str


class ScoreResponse(Schema):
    passport_id: int
    address: str
    score: float


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        try:
            key = request.META["HTTP_AUTHORIZATION"].split()[1]
            api_key = AccountAPIKey.objects.get_from_key(key)

            user_account = api_key.account

            if user_account:
                return user_account
        except AccountAPIKey.DoesNotExist:
            raise Unauthorized()


@api.post("/submit-passport", auth=ApiKey())
def submit_passport(request, payload: SubmitPassportPayload) -> List[ScoreResponse]:
    if get_signer(payload.signature) != payload.address:
        raise InvalidSignerException()

    did = get_did(payload.address)

    # Passport contents read from ceramic
    passport = get_passport(did)

    # TODO Deduplicate passport according to selected deduplication rule

    if not verify_issuer(passport):
        raise InvalidSignerException()

    # Get community object
    user_community = get_object_or_404(
        Community, id=payload.community, account=request.auth
    )

    try:
        # Save passport to Community database (related to community by community_id)
        db_passport = Passport.objects.create(
            passport=passport, address=payload.address.lower(), community=user_community
        )
        db_passport.save()

        for stamp in passport["stamps"]:
            stamp_return_errors = async_to_sync(validate_credential)(
                did, stamp["credential"]
            )
            stamp_expiration_date = datetime.strptime(
                stamp["credential"]["expirationDate"], "%Y-%m-%dT%H:%M:%SZ"
            )
            # check that expiration date is not in the past
            stamp_is_expired = stamp_expiration_date < datetime.now()
            if len(stamp_return_errors) == 0 and stamp_is_expired == False:
                db_stamp = Stamp.objects.create(
                    hash=stamp["credential"]["credentialSubject"]["hash"],
                    provider=stamp["provider"],
                    credential=stamp["credential"],
                    passport=db_passport,
                )
                db_stamp.save()

        scorer = user_community.get_scorer()
        scores = scorer.compute_score([db_passport.id])

        score, _ = Score.objects.update_or_create(
            passport_id=db_passport.id, defaults=dict(score=scores[0])
        )

        return [
            {
                "passport_id": score.passport.id,
                "address": score.passport.address,
                "score": score.score,
            }
            for s in scores
        ]
    except Exception as e:
        InvalidPassportCreationException()

@api.get("/score/{path:address}/{path:community_id}", auth=ApiKey())
def get_score(request, address: str, community_id: int):
    print("address", address, "community_iasdfasfdasd", community_id)
    community = Community.objects.get(id=community_id)
    passport = Passport.objects.get(address=address, community=community)
    score = Score.objects.get(passport=passport)
    return {"score": score.score}
