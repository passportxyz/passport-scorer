"""Ceramic Cache API"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Type

import jwt
import requests
from asgiref.sync import async_to_sync
from django.conf import settings
from scorer.settings.base import get_rpc_url_for_chain
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from eth_account.messages import encode_defunct
from ninja import Router
from ninja_extra import status
from ninja_extra.exceptions import APIException
from ninja_extra.security import HttpBearer
from ninja_jwt.exceptions import InvalidToken, TokenError
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import RefreshToken, Token
from siwe import SiweMessage
from web3 import Web3

import api_logging as logging
import tos.api
import tos.schema
from account.models import Account, Community, Nonce
from ceramic_cache.utils import get_utc_time
from registry.api.utils import (
    is_valid_address,
)
from registry.api.v1 import (
    DetailedScoreResponse,
    ErrorMessageResponse,
)
from registry.exceptions import (
    InvalidAddressException,
    InvalidCommunityScoreRequestException,
    NotFoundApiException,
)
from registry.human_points_utils import get_possible_points_data, get_user_points_data
from registry.models import HumanPointsConfig, Score
from stake.api import get_gtc_stake_for_address
from stake.schema import StakeResponse
from v2.api.api_stamps import format_v2_score_response, handle_scoring_for_account
from v2.schema import V2ScoreResponse

from ..exceptions import (
    InternalServerException,
    InvalidDeleteCacheRequestException,
    TooManyStampsException,
)
from ..models import CeramicCache
from ..utils import validate_dag_jws_payload
from .schema import (
    AccessTokenResponse,
    CacaoVerifySubmit,
    CachedStampResponse,
    CacheStampPayload,
    CalcScorePayload,
    ComporeDBStatusResponse,
    ComposeDBStatusPayload,
    DeleteStampPayload,
    GetStampResponse,
    GetStampsWithInternalV2ScoreResponse,
    GetStampsWithV2ScoreResponse,
    InternalV2ScoreResponse,
    SiweVerifySubmit,
)

log = logging.getLogger(__name__)

router = Router()


def get_address_from_did(did: str):
    return did.split(":")[-1]


class JWTDidAuthentication:
    """
    This authentication class will validate an access token that contains a claim named `did`
    and will save that value in `request.did`

    Supports two token types:
    1. RS256 (SIWE) - Verified using SIWE_JWT_PUBLIC_KEY
    2. HS256 (legacy ninja_jwt) - Verified using SECRET_KEY
    """

    def __init__(self) -> None:
        super().__init__()
        self.user_model = get_user_model()

    @classmethod
    def get_validated_token(cls, raw_token) -> Type[Token]:
        """
        Validates an encoded JSON web token and returns a validated token
        wrapper object.

        First tries RS256 (SIWE tokens), then falls back to HS256 (legacy ninja_jwt).
        """
        messages = []

        # First, try RS256 SIWE token validation
        if settings.SIWE_JWT_PUBLIC_KEY:
            try:
                payload = jwt.decode(
                    raw_token,
                    settings.SIWE_JWT_PUBLIC_KEY,
                    algorithms=["RS256"],
                    issuer="passport-scorer",
                )
                # Return a dict-like object with the 'did' claim
                return payload
            except jwt.exceptions.PyJWTError as e:
                messages.append(
                    {
                        "token_class": "SIWE_RS256",
                        "token_type": "access",
                        "message": str(e),
                    }
                )

        # Fall back to HS256 (legacy ninja_jwt tokens)
        for AuthToken in api_settings.AUTH_TOKEN_CLASSES:
            try:
                ret = AuthToken(raw_token)
                return ret
            except TokenError as e:
                messages.append(
                    {
                        "token_class": AuthToken.__name__,
                        "token_type": AuthToken.token_type,
                        "message": e.args[0],
                    }
                )

        raise InvalidToken(
            {
                "detail": "Given token not valid for any token type",
                "messages": messages,
            }
        )

    def jwt_authenticate(self, request: HttpRequest, token: str) -> Type[AbstractUser]:
        request.did = None
        validated_token = self.get_validated_token(token)
        request.did = validated_token["did"]
        return request


class JWTDidAuth(JWTDidAuthentication, HttpBearer):
    """
    This authentication class to check for did claim in the token
    """

    def authenticate(self, request: HttpRequest, token: str) -> Any:
        return self.jwt_authenticate(request, token)


@router.post(
    "stamps/bulk",
    response={201: GetStampsWithInternalV2ScoreResponse},
    auth=JWTDidAuth(),
)
def cache_stamps(request, payload: List[CacheStampPayload]):
    try:
        address = get_address_from_did(request.did)

        return handle_add_stamps(
            address,
            payload,
            CeramicCache.SourceApp.PASSPORT,
            settings.CERAMIC_CACHE_SCORER_ID,
        )

    except Exception as e:
        raise e


def handle_add_stamps_only(
    address,
    payload: List[CacheStampPayload],
    source_app: CeramicCache.SourceApp,
    alternate_scorer_id: Optional[int] = None,
) -> GetStampResponse:
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    now = get_utc_time()

    existing_stamps = CeramicCache.objects.filter(
        address=address,
        provider__in=[p.provider for p in payload],
        type=CeramicCache.StampType.V1,
        deleted_at__isnull=True,
    )

    existing_stamps.update(updated_at=now, deleted_at=now)

    new_stamp_objects = [
        CeramicCache(
            type=CeramicCache.StampType.V1,
            address=address,
            provider=p.provider,
            stamp=p.stamp,
            proof_value=p.stamp["proof"]["proofValue"],
            updated_at=now,
            compose_db_save_status=CeramicCache.ComposeDBSaveStatus.PENDING,
            issuance_date=p.stamp.get("issuanceDate", None),
            expiration_date=p.stamp.get("expirationDate", None),
            source_app=source_app,
            source_scorer_id=alternate_scorer_id,
        )
        for p in payload
    ]

    CeramicCache.objects.bulk_create(new_stamp_objects)

    updated_passport_state = CeramicCache.objects.filter(
        address=address,
        type=CeramicCache.StampType.V1,
        deleted_at__isnull=True,
        revocation__isnull=True,
    )

    return GetStampResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address,
                provider=stamp.provider,
                stamp=stamp.stamp,
                id=stamp.pk,
            )
            for stamp in updated_passport_state
        ],
    )


def handle_add_stamps(
    address,
    payload: List[CacheStampPayload],
    stamp_creator: CeramicCache.SourceApp,
    alternate_scorer_id: Optional[int] = None,
) -> GetStampsWithInternalV2ScoreResponse:
    stamps_response = handle_add_stamps_only(
        address, payload, stamp_creator, alternate_scorer_id
    )
    scorer_id = alternate_scorer_id or settings.CERAMIC_CACHE_SCORER_ID
    return GetStampsWithInternalV2ScoreResponse(
        success=stamps_response.success,
        stamps=stamps_response.stamps,
        score=get_detailed_score_response_for_address(address, scorer_id=scorer_id),
    )


@router.patch(
    "stamps/bulk",
    response={200: GetStampsWithInternalV2ScoreResponse},
    auth=JWTDidAuth(),
)
def patch_stamps(request, payload: List[CacheStampPayload]):
    try:
        address = get_address_from_did(request.did)
        return handle_patch_stamps(address, payload)

    except Exception as exc:
        log.error(
            "Failed patch_stamps request: '%s'",
            [p.model_dump_json() for p in payload],
            exc_info=True,
        )
        raise InternalServerException() from exc


def handle_patch_stamps(
    address: str, payload: List[CacheStampPayload]
) -> GetStampsWithInternalV2ScoreResponse:
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    now = get_utc_time()

    # Soft delete all, the ones with a stamp defined will be re-created
    providers_to_delete = [p.provider for p in payload]

    if providers_to_delete:
        stamps = CeramicCache.objects.filter(
            address=address,
            provider__in=providers_to_delete,
            deleted_at__isnull=True,
        )
        stamps.update(updated_at=now, deleted_at=now)

    new_stamp_objects = [
        CeramicCache(
            type=CeramicCache.StampType.V1,
            address=address,
            provider=p.provider,
            stamp=p.stamp,
            proof_value=p.stamp["proof"]["proofValue"],
            updated_at=now,
            compose_db_save_status=CeramicCache.ComposeDBSaveStatus.PENDING,
            issuance_date=p.stamp.get("issuanceDate", None),
            expiration_date=p.stamp.get("expirationDate", None),
        )
        for p in payload
        if p.stamp
    ]

    if new_stamp_objects:
        CeramicCache.objects.bulk_create(new_stamp_objects)

    updated_passport_state = CeramicCache.objects.filter(
        address=address,
        type=CeramicCache.StampType.V1,
        deleted_at__isnull=True,
        revocation__isnull=True,
    )

    return GetStampsWithInternalV2ScoreResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address,
                provider=stamp.provider,
                stamp=stamp.stamp,
                id=stamp.pk,
            )
            for stamp in updated_passport_state
        ],
        score=get_detailed_score_response_for_address(
            address, settings.CERAMIC_CACHE_SCORER_ID
        ),
    )


@router.patch(
    "stamps/bulk/meta/compose-db", response=ComporeDBStatusResponse, auth=JWTDidAuth()
)
def update_compose_db_status(request, payload: List[ComposeDBStatusPayload]):
    try:
        address = get_address_from_did(request.did)
        return handle_update_compose_db_status(address, payload)
    except Exception as e:
        raise e


def handle_update_compose_db_status(
    address: str, payload: List[ComposeDBStatusPayload]
):
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    now = get_utc_time()

    stamp_objects = CeramicCache.objects.filter(
        address=address,
        id__in=[stamp.id for stamp in payload],
        deleted_at__isnull=True,
        compose_db_save_status=CeramicCache.ComposeDBSaveStatus.PENDING,
        type=CeramicCache.StampType.V1,
    )

    pending_status_updates = payload.copy()
    for stamp_object in stamp_objects:
        for idx, status_update in enumerate(pending_status_updates):
            if str(stamp_object.pk) == str(status_update.id):
                stamp_object.updated_at = now
                stamp_object.compose_db_save_status = (
                    status_update.compose_db_save_status
                )

                if status_update.compose_db_stream_id:
                    stamp_object.compose_db_stream_id = (
                        status_update.compose_db_stream_id
                    )

                pending_status_updates.pop(idx)
                break

    CeramicCache.objects.bulk_update(
        stamp_objects,
        [
            "updated_at",
            "compose_db_save_status",
            "compose_db_stream_id",
        ],
    )

    return {
        "updated": [stamp_object.pk for stamp_object in stamp_objects],
    }


@router.delete("stamps/bulk", response=GetStampResponse, auth=JWTDidAuth())
def delete_stamps(request, payload: List[DeleteStampPayload]):
    try:
        address = get_address_from_did(request.did)
        return handle_delete_stamps(address, payload)
    except Exception as e:
        raise e


def handle_delete_stamps(
    address: str, payload: List[DeleteStampPayload]
) -> GetStampsWithInternalV2ScoreResponse:
    if len(payload) > settings.MAX_BULK_CACHE_SIZE:
        raise TooManyStampsException()

    stamps = CeramicCache.objects.filter(
        # We do not filter by type. The thinking is: if a user wants to delete a V2 stamp, then he wants to delete both the V1 and V2 stamps ...
        address=address,
        provider__in=[p.provider for p in payload],
        deleted_at__isnull=True,
    )
    if not stamps:
        raise InvalidDeleteCacheRequestException()

    now = get_utc_time()
    stamps.update(deleted_at=now, updated_at=now)

    updated_passport_state = CeramicCache.objects.filter(
        address=address, deleted_at__isnull=True, revocation__isnull=True
    )

    return GetStampsWithInternalV2ScoreResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address,
                provider=stamp.provider,
                stamp=stamp.stamp,
                id=stamp.pk,
            )
            for stamp in updated_passport_state
        ],
        score=get_detailed_score_response_for_address(
            address, settings.CERAMIC_CACHE_SCORER_ID
        ),
    )


class InvalidScorerConfiguration(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Unable to retrieve configured scorer!"


@router.get("weights", response=Dict[str, float])
def get_scorer_weights(request):
    return handle_get_scorer_weights()


def handle_get_scorer_weights(community_id=None) -> Dict[str, float]:
    if not community_id:
        community_id = settings.CERAMIC_CACHE_SCORER_ID

    cache_key = f"ceramic_cache_scorer_weights_{community_id}"
    weights = cache.get(cache_key)
    if weights:
        try:
            return json.loads(weights)
        except Exception:
            log.error("Failed to parse weights from cache!", exc_info=True)

    try:
        community = Community.objects.get(id=community_id)
        weights = community.get_scorer().weights
        # Cache the value for 1 minute
        cache.set(cache_key, json.dumps(weights), 1 * 60)
        return weights

    except Exception:
        msg = f"Unable to retrieve configured scorer! settings.CERAMIC_CACHE_SCORER_ID={settings.CERAMIC_CACHE_SCORER_ID}"
        log.error(msg, exc_info=True)
        raise InvalidScorerConfiguration(msg)


@router.get("stamp", response=GetStampResponse)
def get_stamps(request, address):
    try:
        return handle_get_stamps(address)
    except Exception as e:
        raise e


def handle_get_stamps(address):
    stamps = CeramicCache.objects.filter(
        address=address,
        type=CeramicCache.StampType.V1,
        deleted_at__isnull=True,
        revocation__isnull=True,
    )

    scorer_id = settings.CERAMIC_CACHE_SCORER_ID
    if (
        scorer_id
        and not Score.objects.filter(
            passport__address=address.lower(),
            passport__community_id=scorer_id,
        ).exists()
    ):
        get_detailed_score_response_for_address(address, scorer_id)

    return GetStampResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=stamp.address,
                provider=stamp.provider,
                stamp=stamp.stamp,
                id=stamp.pk,
            )
            for stamp in stamps
        ],
    )


@router.get(
    "/score/{str:address}",
    auth=JWTDidAuth(),
    response=InternalV2ScoreResponse,
)
def get_score(
    request, address: str, alternate_scorer_id: Optional[int] = None
) -> InternalV2ScoreResponse:
    return handle_get_ui_score(address, alternate_scorer_id)


def handle_get_ui_score(
    address: str, alternate_scorer_id: Optional[int]
) -> InternalV2ScoreResponse:
    scorer_id = alternate_scorer_id or settings.CERAMIC_CACHE_SCORER_ID
    lower_address = address.lower()

    if not is_valid_address(lower_address):
        raise InvalidAddressException()

    try:
        # Get community object, for the configured scorer
        user_community = Community.objects.get(id=scorer_id)
        scorer = user_community.get_scorer()
        scorer_type = scorer.type

        score = None
        try:
            score = Score.objects.select_related("passport").get(
                passport__address=lower_address, passport__community=user_community
            )
        except Score.DoesNotExist:
            pass

        # If score is expired re-calculate it
        now = get_utc_time()

        if score is None or (
            score.expiration_date is not None and score.expiration_date < now
        ):
            # This will re-calculate the score and update the expiration date.
            ret = get_detailed_score_response_for_address(address, scorer_id)

            return ret

        # Get points data if community has human_points_program enabled
        points_data = None
        possible_points_data = None
        if settings.HUMAN_POINTS_ENABLED and user_community.human_points_program:
            points_data = get_user_points_data(lower_address)
            multiplier = points_data.get("multiplier", 1)
            possible_points_data = get_possible_points_data(multiplier)

        # Include human points for ceramic-cache endpoints
        return format_v2_score_response(
            score,
            scorer_type,
            points_data,
            possible_points_data,
            include_human_points=True,
        )

    except Community.DoesNotExist as e:
        raise NotFoundApiException(
            "Community matching the configured scorer id does not exist! This is probably a misconfiguration!",
            code=500,
        ) from e
    except Score.DoesNotExist as e:
        raise NotFoundApiException(
            "No score could be found matching the request!"
        ) from e
    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException() from e


@router.post(
    "/score/{str:address}",
    response=InternalV2ScoreResponse,
    auth=JWTDidAuth(),
)
def calc_score(
    request, address: str, payload: CalcScorePayload
) -> InternalV2ScoreResponse:
    return get_detailed_score_response_for_address(address, payload.alternate_scorer_id)


class FailedVerificationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to authorize request"


class DbCacheToken(RefreshToken):
    # Lifetime of the token is set to 7 days (because this is the setting of the CACAO session)
    # But it should ideally be read out of the cacao
    lifetime: timedelta = timedelta(days=7)


@router.post(
    "authenticate",
    response=AccessTokenResponse,
)
def authenticate(request, payload: CacaoVerifySubmit):
    """
    This method will validate a jws created with DagJWS, will validate by forwarding this to our validator
    it and return a JWT token.
    """
    return handle_authenticate(payload)


def generate_access_token_response(user_did: str) -> AccessTokenResponse:
    token = DbCacheToken()
    token["did"] = user_did

    intercom_user_hash = hmac.new(
        bytes(settings.INTERCOM_SECRET_KEY, encoding="utf-8"),
        bytes(user_did, encoding="utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return AccessTokenResponse(
        access=str(token.access_token),
        intercom_user_hash=intercom_user_hash,
    )


def generate_siwe_access_token(user_did: str) -> str:
    """
    Generate RS256 JWT for SIWE authentication using PyJWT directly.
    This token can be verified by IAM using the public key.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "did": user_did,
        "iat": now,
        "exp": now + timedelta(days=7),  # 7-day lifetime like DbCacheToken
        "jti": str(uuid.uuid4()),
        "iss": "passport-scorer",
        "token_type": "access",
    }
    return jwt.encode(payload, settings.SIWE_JWT_PRIVATE_KEY, algorithm="RS256")


def generate_access_token_response_v2(user_did: str) -> AccessTokenResponse:
    """Generate JWT access token for SIWE v2 authentication using RS256"""
    access_token = generate_siwe_access_token(user_did)
    return AccessTokenResponse(access=access_token)


def get_web3_for_chain(chain_id: int) -> Web3:
    """Get Web3 instance for a specific chain with 5-second timeout"""
    rpc_url = get_rpc_url_for_chain(chain_id)
    provider = Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 5})
    return Web3(provider)


def verify_signature_erc6492(
    address: str, message_hash: bytes, signature: str, chain_id: int
) -> bool:
    """
    Verify any signature (EOA or smart wallet) using ERC-6492 Universal Signature Validator.

    ERC-6492 handles:
    - EOA signatures (standard ecrecover)
    - EIP-1271 deployed smart contract signatures
    - EIP-1271 undeployed (counterfactual) smart contract signatures

    Uses the "deployless" approach from Ambire's signature-validator - deploys the validator
    inline during eth_call without needing a pre-deployed contract.
    """
    # Ambire's UniversalSigValidator bytecode for deployless verification
    # From https://github.com/AmbireTech/signature-validator
    UNIVERSAL_VALIDATOR_BYTECODE = bytes.fromhex(
        "60806040523480156200001157600080fd5b50604051620007003803806200070083398101604081905262000034916200056f565b6000620000438484846200004f565b9050806000526001601ff35b600080846001600160a01b0316803b806020016040519081016040528181526000908060200190933c90507f6492649264926492649264926492649264926492649264926492649264926492620000a68462000451565b036200021f57600060608085806020019051810190620000c79190620005ce565b8651929550909350915060000362000192576000836001600160a01b031683604051620000f5919062000643565b6000604051808303816000865af19150503d806000811462000134576040519150601f19603f3d011682016040523d82523d6000602084013e62000139565b606091505b5050905080620001905760405162461bcd60e51b815260206004820152601e60248201527f5369676e617475726556616c696461746f723a206465706c6f796d656e74000060448201526064015b60405180910390fd5b505b604051630b135d3f60e11b808252906001600160a01b038a1690631626ba7e90620001c4908b90869060040162000661565b602060405180830381865afa158015620001e2573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906200020891906200069d565b6001600160e01b031916149450505050506200044a565b805115620002b157604051630b135d3f60e11b808252906001600160a01b03871690631626ba7e9062000259908890889060040162000661565b602060405180830381865afa15801562000277573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906200029d91906200069d565b6001600160e01b031916149150506200044a565b8251604114620003195760405162461bcd60e51b815260206004820152603a6024820152600080516020620006e083398151915260448201527f3a20696e76616c6964207369676e6174757265206c656e677468000000000000606482015260840162000187565b620003236200046b565b506020830151604080850151855186939260009185919081106200034b576200034b620006c9565b016020015160f81c9050601b81148015906200036b57508060ff16601c14155b15620003cf5760405162461bcd60e51b815260206004820152603b6024820152600080516020620006e083398151915260448201527f3a20696e76616c6964207369676e617475726520762076616c75650000000000606482015260840162000187565b6040805160008152602081018083528a905260ff83169181019190915260608101849052608081018390526001600160a01b038a169060019060a0016020604051602081039080840390855afa1580156200042e573d6000803e3d6000fd5b505050602060405103516001600160a01b031614955050505050505b9392505050565b60006020825110156200046357600080fd5b508051015190565b60405180606001604052806003906020820280368337509192915050565b6001600160a01b03811681146200049f57600080fd5b50565b634e487b7160e01b600052604160045260246000fd5b60005b83811015620004d5578181015183820152602001620004bb565b50506000910152565b600082601f830112620004f057600080fd5b81516001600160401b03808211156200050d576200050d620004a2565b604051601f8301601f19908116603f01168101908282118183101715620005385762000538620004a2565b816040528381528660208588010111156200055257600080fd5b62000565846020830160208901620004b8565b9695505050505050565b6000806000606084860312156200058557600080fd5b8351620005928162000489565b6020850151604086015191945092506001600160401b03811115620005b657600080fd5b620005c486828701620004de565b9150509250925092565b600080600060608486031215620005e457600080fd5b8351620005f18162000489565b60208501519093506001600160401b03808211156200060f57600080fd5b6200061d87838801620004de565b935060408601519150808211156200063457600080fd5b50620005c486828701620004de565b6000825162000657818460208701620004b8565b9190910192915050565b828152604060208201526000825180604084015262000688816060850160208701620004b8565b601f01601f1916919091016060019392505050565b600060208284031215620006b057600080fd5b81516001600160e01b0319811681146200044a57600080fd5b634e487b7160e01b600052603260045260246000fdfe5369676e617475726556616c696461746f72237265636f7665725369676e6572"
    )

    try:
        w3 = get_web3_for_chain(chain_id)
        checksum_address = Web3.to_checksum_address(address)

        # Prepare signature bytes
        sig_bytes = bytes.fromhex(signature.replace("0x", ""))

        # Check if signature is ERC-6492 wrapped (ends with magic bytes)
        ERC6492_MAGIC = bytes.fromhex("6492649264926492649264926492649264926492649264926492649264926492")
        is_6492_wrapped = sig_bytes[-32:] == ERC6492_MAGIC if len(sig_bytes) >= 32 else False
        log.debug(f"Signature is ERC-6492 wrapped: {is_6492_wrapped}, length: {len(sig_bytes)} bytes")

        # ABI encode constructor parameters: (address _signer, bytes32 _hash, bytes _signature)
        encoded_params = w3.codec.encode(
            ['address', 'bytes32', 'bytes'],
            [checksum_address, message_hash, sig_bytes]
        )

        # Concatenate bytecode + encoded params for deployless verification
        call_data = UNIVERSAL_VALIDATOR_BYTECODE + encoded_params

        log.info(f"ERC-6492 deployless call: chain={chain_id}, address={checksum_address}, hash={message_hash.hex()}, sig_len={len(sig_bytes)}")

        try:
            # eth_call with no 'to' address deploys and executes the bytecode inline
            result = w3.eth.call({'data': call_data})
            # Result is 0x01 for valid, 0x00 for invalid
            is_valid = result == b'\x01'
            log.info(f"ERC-6492 deployless result on chain {chain_id}: {result.hex()} (valid={is_valid})")
            return is_valid
        except Exception as call_error:
            log.error(f"ERC-6492 eth_call failed on chain {chain_id}: {call_error}")
            return False
    except Exception as e:
        log.error(
            f"Error verifying ERC-6492 signature for {address} on chain {chain_id}: {e}",
            exc_info=True,
        )
        return False


def handle_authenticate(payload: CacaoVerifySubmit) -> AccessTokenResponse:
    # First validate the payload
    # This will ensure that the payload signature was made for our unique nonce
    try:
        if not Nonce.use_nonce(payload.nonce):
            log.error("Invalid or expired nonce: '%s'", payload.nonce)
            raise FailedVerificationException(detail="Invalid nonce!")

        if not validate_dag_jws_payload({"nonce": payload.nonce}, payload.payload):
            log.error("Failed to validate nonce: '%s'", payload.nonce)
            raise FailedVerificationException(detail="Invalid nonce or payload!")
    except Exception as exc:
        log.error("Failed authenticate request: '%s'", payload.dict(), exc_info=True)
        raise FailedVerificationException(detail="Invalid nonce or payload!") from exc

    try:
        res = requests.post(
            settings.VERIFIER_URL,
            json={
                "signatures": payload.signatures,
                "payload": payload.payload,
                "cid": payload.cid,
                "cacao": payload.cacao,
                "issuer": payload.issuer,
            },
        )

        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "ok":
                return generate_access_token_response(payload.issuer)

        log.error(
            "Failed to validate authentication payload (jws)! Response: %s\n%s",
            res,
            res.json(),
        )
        raise FailedVerificationException(detail=f"JWS validation failed: {res.json()}")

    except APIException:
        # re-raise API exceptions
        raise
    except Exception as esc:
        log.error(
            "Failed to authenticate request (verify_jws failed): '%s'",
            payload.dict(),
            exc_info=True,
        )
        raise APIException(
            detail=f"Failed to authenticate request: {str(esc)}"
        ) from esc


def get_detailed_score_response_for_address(
    address: str, scorer_id: Optional[int]
) -> InternalV2ScoreResponse:
    if not scorer_id:
        raise InternalServerException("Scorer ID not set")

    account = get_object_or_404(Account, community__id=scorer_id)

    # Include human points for ceramic-cache endpoints
    score = async_to_sync(handle_scoring_for_account)(
        address, str(scorer_id), account, include_human_points=True
    )

    return score


@router.get(
    "/stake/gtc",
    response={
        200: StakeResponse,
        400: ErrorMessageResponse,
    },
    auth=JWTDidAuth(),
)
def get_staked_gtc(request) -> StakeResponse:
    address = get_address_from_did(request.did)
    get_stake_response = get_gtc_stake_for_address(address)
    response = StakeResponse(items=get_stake_response)
    return response


@router.get(
    "/tos/accepted/{str:tos_type}/{str:address}",
    auth=JWTDidAuth(),
    response={
        200: tos.schema.TosAccepted,
        400: ErrorMessageResponse,
    },
    summary="Check that tos was accepted",
)
def tos_check_accepted(request, tos_type: str, address: str) -> tos.schema.TosAccepted:
    return tos.api.check_tos_accepted(tos_type, address)


@router.get(
    "/tos/message-to-sign/{str:tos_type}/{str:address}",
    auth=JWTDidAuth(),
    response={
        200: tos.schema.TosToSign,
        400: ErrorMessageResponse,
    },
    summary="Get the tos message to sign",
)
def get_tos_to_sign(request, tos_type: str, address: str) -> tos.schema.TosToSign:
    return tos.api.get_tos_to_sign(tos_type, address)


@router.post(
    "/tos/signed-message/{str:tos_type}/{str:address}",
    auth=JWTDidAuth(),
    response={
        200: None,
        400: ErrorMessageResponse,
    },
    summary="Accept the tos",
)
def accept_tos(
    request, tos_type: str, address: str, payload: tos.schema.TosSigned
) -> None:
    tos.api.accept_tos(payload)


@router.post(
    "authenticate/v2",
    response=AccessTokenResponse,
)
def authenticate_v2(request, payload: SiweVerifySubmit):
    """
    SIWE-based authentication endpoint that supports both EOA and smart contract wallets.
    Accepts SIWE message + signature instead of DagJWS/CACAO.
    Returns JWT with `did` claim in format `did:pkh:eip155:1:0xADDRESS`
    """
    return handle_authenticate_v2(payload)


def handle_authenticate_v2(payload: SiweVerifySubmit) -> AccessTokenResponse:
    """
    Handle SIWE v2 authentication:
    1. Validate nonce (use once, 5-minute TTL)
    2. Parse and verify SIWE message
    3. Verify signature using ERC-6492 (handles EOA + smart wallets universally)
    4. Return JWT with did claim
    """
    try:
        # Debug: Log the full payload for smart wallet signature debugging
        log.debug(f"Received authenticate_v2 payload: {payload.dict()}")

        address_raw = payload.message.get("address", "")
        nonce = payload.message.get("nonce")
        chain_id = payload.message.get("chainId", 1)

        if not address_raw or not nonce:
            log.error("Missing address or nonce in SIWE message")
            raise FailedVerificationException(detail="Missing address or nonce!")

        # Convert to EIP-55 checksum format (required by SIWE library)
        # This handles any input format: lowercase, uppercase, or already checksummed
        try:
            address = Web3.to_checksum_address(address_raw)
        except ValueError:
            log.error("Invalid Ethereum address: '%s'", address_raw)
            raise FailedVerificationException(detail="Invalid address format!")

        # Validate and consume nonce (5-minute TTL)
        if not Nonce.use_nonce(nonce):
            log.error("Invalid or expired nonce: '%s'", nonce)
            raise FailedVerificationException(detail="Invalid nonce!")

        # Convert message dict to SIWE message format
        # Include ALL optional fields to ensure message text matches what was signed
        siwe_message_dict = {
            "domain": payload.message.get("domain"),
            "address": address,  # EIP-55 checksum format (converted above)
            "statement": payload.message.get("statement"),
            "uri": payload.message.get("uri"),
            "version": payload.message.get("version"),
            "chain_id": chain_id,
            "nonce": nonce,
            "issued_at": payload.message.get("issuedAt"),
        }

        # Add optional SIWE fields if present in the original message
        if payload.message.get("expirationTime"):
            siwe_message_dict["expiration_time"] = payload.message.get("expirationTime")
        if payload.message.get("notBefore"):
            siwe_message_dict["not_before"] = payload.message.get("notBefore")
        if payload.message.get("requestId"):
            siwe_message_dict["request_id"] = payload.message.get("requestId")
        if payload.message.get("resources"):
            siwe_message_dict["resources"] = payload.message.get("resources")

        # Reconstruct the full SIWE message text
        siwe_msg = SiweMessage(**siwe_message_dict)
        message_text = siwe_msg.prepare_message()

        # Create EIP-191 prefixed message hash for ERC-6492 verification
        # encode_defunct returns SignableMessage with version + header + body
        # We need to hash the FULL prefixed message: \x19Ethereum Signed Message:\n{len}{message}
        prefixed_message = encode_defunct(text=message_text)
        full_prefixed_data = prefixed_message.version + prefixed_message.header + prefixed_message.body
        message_hash = Web3.keccak(full_prefixed_data)

        # Debug logging to help diagnose smart wallet signature issues
        log.info(f"Original payload message: {payload.message}")
        log.info(f"Reconstructed SIWE message text:\n{message_text}")
        log.info(f"Message hash (hex): {message_hash.hex()}")

        # Try standard EOA ecrecover first (faster, no RPC needed)
        from eth_account import Account
        signature_valid = False
        try:
            recovered = Account.recover_message(prefixed_message, signature=payload.signature)
            signature_valid = recovered.lower() == address.lower()
            if signature_valid:
                log.info(f"Signature verified via ecrecover for {address}")
        except Exception as e:
            log.debug(f"ecrecover failed, trying ERC-6492: {e}")

        # Fallback to ERC-6492 for smart wallets
        # Try verification on multiple chains since smart wallets may only be deployed on specific chains
        # The factory contract in the ERC-6492 signature might only exist on certain chains
        if not signature_valid:
            # Chains where smart wallets are commonly deployed (Base, mainnet, Optimism, Arbitrum)
            # Try the specified chain first, then others
            chains_to_try = [chain_id]
            for fallback_chain in [8453, 1, 10, 42161]:  # Base, mainnet, OP, Arb
                if fallback_chain not in chains_to_try:
                    chains_to_try.append(fallback_chain)

            for try_chain in chains_to_try:
                log.info(f"Trying ERC-6492 verification for {address} on chain {try_chain}")
                signature_valid = verify_signature_erc6492(
                    address, message_hash, payload.signature, try_chain
                )
                if signature_valid:
                    log.info(f"ERC-6492 verification succeeded on chain {try_chain}")
                    break

        if not signature_valid:
            log.error(f"Signature verification failed for {address}")
            raise FailedVerificationException(detail="Invalid signature!")

        # Generate DID (always use eip155:1 for consistent identifier format)
        # Lowercase for DID consistency (address is kept in checksum format above for SIWE)
        user_did = f"did:pkh:eip155:1:{address.lower()}"

        # Generate and return JWT token
        return generate_access_token_response_v2(user_did)

    except FailedVerificationException:
        raise
    except Exception as exc:
        log.error("Failed authenticate_v2 request: '%s'", payload.dict(), exc_info=True)
        raise FailedVerificationException(detail="Authentication failed!") from exc
