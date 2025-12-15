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
    return jwt.encode(
        payload,
        settings.SIWE_JWT_PRIVATE_KEY,
        algorithm="RS256"
    )


def generate_access_token_response_v2(user_did: str) -> AccessTokenResponse:
    """Generate JWT access token for SIWE v2 authentication using RS256"""
    access_token = generate_siwe_access_token(user_did)
    return AccessTokenResponse(access=access_token)


def get_web3_for_chain(chain_id: int) -> Web3:
    """Get Web3 instance for a specific chain with 5-second timeout"""
    rpc_url = settings.get_rpc_url_for_chain(chain_id)
    provider = Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 5})
    return Web3(provider)


def verify_signature_erc6492(address: str, message_hash: bytes, signature: str, chain_id: int) -> bool:
    """
    Verify any signature (EOA or smart wallet) using ERC-6492 Universal Signature Validator.

    ERC-6492 handles:
    - EOA signatures (standard ecrecover)
    - EIP-1271 deployed smart contract signatures
    - EIP-1271 undeployed (counterfactual) smart contract signatures

    The validator contract is deployed at the same address on all EVM chains via CREATE2.
    """
    # ERC-6492 UniversalSigValidator ABI - just the isValidSig function
    UNIVERSAL_VALIDATOR_ABI = [{
        "inputs": [
            {"name": "_signer", "type": "address"},
            {"name": "_hash", "type": "bytes32"},
            {"name": "_signature", "type": "bytes"}
        ],
        "name": "isValidSig",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }]

    try:
        w3 = get_web3_for_chain(chain_id)
        checksum_address = Web3.to_checksum_address(address)
        validator_address = Web3.to_checksum_address(settings.ERC6492_UNIVERSAL_VALIDATOR)

        # Create contract instance
        contract = w3.eth.contract(address=validator_address, abi=UNIVERSAL_VALIDATOR_ABI)

        # Prepare signature bytes
        sig_bytes = bytes.fromhex(signature.replace("0x", ""))

        # Call isValidSig - this handles EOA, deployed smart wallets, and undeployed smart wallets
        # We use eth_call to simulate the transaction without actually sending it
        result = contract.functions.isValidSig(
            checksum_address,
            message_hash,
            sig_bytes
        ).call()

        return result
    except Exception as e:
        log.error(f"Error verifying ERC-6492 signature for {address} on chain {chain_id}: {e}", exc_info=True)
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
        address = payload.message.get("address", "").lower()
        nonce = payload.message.get("nonce")
        chain_id = payload.message.get("chainId", 1)

        if not address or not nonce:
            log.error("Missing address or nonce in SIWE message")
            raise FailedVerificationException(detail="Missing address or nonce!")

        # Validate and consume nonce (5-minute TTL)
        if not Nonce.use_nonce(nonce):
            log.error("Invalid or expired nonce: '%s'", nonce)
            raise FailedVerificationException(detail="Invalid nonce!")

        # Convert message dict to SIWE message format
        siwe_message_dict = {
            "domain": payload.message.get("domain"),
            "address": address,
            "statement": payload.message.get("statement"),
            "uri": payload.message.get("uri"),
            "version": payload.message.get("version"),
            "chain_id": chain_id,
            "nonce": nonce,
            "issued_at": payload.message.get("issuedAt"),
        }

        # Reconstruct the full SIWE message text
        siwe_msg = SiweMessage(**siwe_message_dict)
        message_text = siwe_msg.prepare_message()

        # Create EIP-191 prefixed message hash for ERC-6492 verification
        message_hash = encode_defunct(text=message_text).body

        # Verify signature using ERC-6492 Universal Validator
        # This handles EOA, deployed smart wallets, AND undeployed smart wallets
        log.info(f"Verifying signature for {address} on chain {chain_id} using ERC-6492")
        if not verify_signature_erc6492(address, message_hash, payload.signature, chain_id):
            log.error(f"ERC-6492 signature verification failed for {address}")
            raise FailedVerificationException(detail="Invalid signature!")

        # Generate DID (always use eip155:1 for consistent identifier format)
        user_did = f"did:pkh:eip155:1:{address}"

        # Generate and return JWT token
        return generate_access_token_response_v2(user_did)

    except FailedVerificationException:
        raise
    except Exception as exc:
        log.error("Failed authenticate_v2 request: '%s'", payload.dict(), exc_info=True)
        raise FailedVerificationException(detail="Authentication failed!") from exc
