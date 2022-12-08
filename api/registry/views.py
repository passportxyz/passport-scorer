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

# --- Models
from account.models import Account, AccountAPIKey, Community
from registry.models import Passport, Stamp
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

class SubmitPassportPayload(Schema):
    address: str
    signature: str
    community: str


from ninja.security import APIKeyHeader


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        print("*" * 80)
        print(request)
        print(request.META)
        print(key)
        print(get_headers(request))

        if key == "supersecret":
            return key

api_key = ApiKey()

@api.post("/submit-passport")
def submit_passport(request, payload: SubmitPassportPayload):
    if get_signer(payload.signature) != payload.address:
        raise InvalidSignerException()

    did = get_did(payload.address)

    # Passport contents read from ceramic
    passport = get_passport(did)
    print("PASSPORT:", passport)
    # TODO Deduplicate passport according to selected deduplication rule

    if not verify_issuer(passport):
        raise InvalidSignerException()

    try:
        # Get community object
        community=Community.objects.get(id=payload.community)
        # Save passport to Community database (related to community by community_id)
        db_passport = Passport.objects.create(passport=passport, did=did, community=community)
        db_passport.save()

        for stamp in passport["stamps"]:
            stamp_return_errors = async_to_sync(validate_credential)(did, stamp["credential"])
            stamp_expiration_date = datetime.strptime(stamp["credential"]["expirationDate"], '%Y-%m-%dT%H:%M:%SZ')
            # check that expuriration date is not in the past
            stamp_is_expired = stamp_expiration_date < datetime.now()
            if len(stamp_return_errors) == 0 and stamp_is_expired == False:
                db_stamp = Stamp.objects.create(hash=stamp["credential"]["credentialSubject"]["hash"], provider=stamp["provider"], credential=stamp["credential"], passport=db_passport)
                db_stamp.save()
        

        return {"working": True}
    except Exception as e:
        InvalidPassportCreationException()
    