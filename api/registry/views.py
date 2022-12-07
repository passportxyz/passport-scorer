# --- Python imports
import random
import hashlib
import string
import json
import logging
from typing import cast, List
from django.shortcuts import get_object_or_404

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

log = logging.getLogger(__name__)
api = NinjaExtraAPI(urls_namespace="registry")

class InvalidSignerException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Address does not match signature."

class SubmitPassportPayload(Schema):
    address: str
    signature: str

@api.post("/submit-passport")
def submit_passport(request, payload: SubmitPassportPayload):
    if get_signer(payload.signature) != payload.address:
        raise InvalidSignerException()

    did = get_did(payload.address)
    passport = get_passport(did)

    print("**Passport --->", passport)
    # Passport contents read from ceramic

    # Deduplicate passport according to selected deduplication rule

    # Save passport to Community database (related to community by community_id)

    if not verify_issuer(passport):
        raise InvalidSignerException()

    db_passport = Passport.objects.create(passport=passport, did=did)
    db_passport.save()

    for stamp in passport["stamps"]:
        db_stamp = Stamp.objects.create(hash=stamp["credential"]["credentialSubject"]["hash"], provider=stamp["provider"], credential=stamp["credential"], passport=db_passport)
        db_stamp.save()
    

    return {"working": True}
    