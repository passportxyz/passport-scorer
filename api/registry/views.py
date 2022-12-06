# --- Python imports
import random
import hashlib
import string
import logging
from typing import cast, List
from django.shortcuts import get_object_or_404

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
from account.models import Account, AccountAPIKey, Community
from django.contrib.auth import get_user_model
from django.http import HttpResponse

log = logging.getLogger(__name__)
api = NinjaExtraAPI(urls_namespace="registry")

@api.get("/submit-passport")
def working(request):
    return {"working": True}
    