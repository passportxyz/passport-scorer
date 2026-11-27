"""Cache credentials issued to the exact identity in a deployed-wallet access token."""

import os
import re
from datetime import datetime, timezone

import jwt
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import connection, transaction
from django.db.models import F
from django.db.models.fields.json import KT
from ninja import Schema
from ninja.errors import HttpError
from ninja.security import HttpBearer

from account.models import Community
from ceramic_cache.models import (
    CeramicCache,
    ChainWalletStamp,
    EffectiveChainWalletStamp,
    Revocation,
)
from registry.exceptions import NotFoundApiException, Unauthorized
from registry.utils import validate_credential
from v2.chain_wallet_scoring import score_chain_wallet
from v2.schema import ChainWalletScoreResponse

from .router import api_router

DID_PATTERN = re.compile(r"did:pkh:eip155:([1-9][0-9]{0,15}):(0x[0-9a-f]{40})")


class ScopedCacheAuth(HttpBearer):
    def authenticate(self, request, token):
        if (
            os.environ.get("CHAIN_WALLET_SCORING_ENABLED") != "true"
            or not settings.SIWE_JWT_PUBLIC_KEY
        ):
            raise Unauthorized()
        try:
            claims = jwt.decode(
                token,
                settings.SIWE_JWT_PUBLIC_KEY,
                algorithms=["RS256"],
                issuer="passport-scorer",
                options={"require": ["exp", "iat", "did"]},
            )
        except jwt.PyJWTError as exc:
            raise Unauthorized() from exc
        did = claims["did"]
        match = DID_PATTERN.fullmatch(did) if isinstance(did, str) else None
        if (
            claims.get("chain_wallet") is not True
            or claims.get("token_type") != "access"
            or not match
        ):
            raise Unauthorized()
        chain_id, address = int(match[1]), match[2]
        if chain_id > 9007199254740991:
            raise Unauthorized()
        return chain_id, address, did


class WalletStampUpdate(Schema):
    provider: str
    stamp: dict | None = None


class CachedWalletStamp(Schema):
    id: int
    address: str
    provider: str
    stamp: dict


class WalletStampResponse(Schema):
    success: bool = True
    stamps: list[CachedWalletStamp]


def active_wallet_stamps(chain_id, address):
    return ChainWalletStamp.objects.filter(
        chain_id=chain_id, address=address, deleted_at__isnull=True
    )


def stamp_response(chain_id, address):
    active = EffectiveChainWalletStamp.objects.filter(
        chain_id=chain_id, address=address
    )
    return WalletStampResponse(
        stamps=list(
            active.order_by("provider").values("id", "address", "provider", "stamp")
        )
    )


@api_router.get("/wallet-stamps", auth=ScopedCacheAuth(), response=WalletStampResponse)
def get_wallet_stamps(request):
    chain_id, address, _ = request.auth
    return stamp_response(chain_id, address)


@api_router.patch(
    "/wallet-stamps", auth=ScopedCacheAuth(), response=WalletStampResponse
)
def update_wallet_stamps(request, updates: list[WalletStampUpdate]):
    chain_id, address, did = request.auth
    providers = {update.provider for update in updates}
    if (
        len(updates) > settings.MAX_BULK_CACHE_SIZE
        or len(providers) != len(updates)
        or any(not provider or len(provider) > 256 for provider in providers)
    ):
        raise HttpError(400, "Invalid wallet stamp update")

    replacements = []
    for update in updates:
        credential = update.stamp
        if credential is None:
            continue
        subject = credential.get("credentialSubject")
        proof = credential.get("proof")
        proof_value = proof.get("proofValue") if isinstance(proof, dict) else None
        if (
            not isinstance(subject, dict)
            or str(subject.get("id", "")).lower() != did
            or subject.get("provider") != update.provider
            or not isinstance(proof_value, str)
            or not 0 < len(proof_value) <= 256
            or credential.get("issuer") not in settings.TRUSTED_IAM_ISSUERS
            or async_to_sync(validate_credential)(did, credential)
        ):
            raise HttpError(400, "Invalid wallet credential")
        replacements.append(
            ChainWalletStamp(
                chain_id=chain_id,
                address=address,
                provider=update.provider,
                stamp=credential,
                proof_value=proof_value,
            )
        )

    with transaction.atomic():
        if providers:
            # Serialize replacements for one wallet, including its first write.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [did]
                )
            if Revocation.objects.filter(
                proof_value__in=[stamp.proof_value for stamp in replacements]
            ).exists():
                raise HttpError(400, "Revoked wallet credential")
            deleted_at = datetime.now(timezone.utc)
            active_wallet_stamps(chain_id, address).filter(
                provider__in=providers
            ).update(deleted_at=deleted_at)
            if chain_id == 1:
                deleted_providers = {
                    update.provider for update in updates if update.stamp is None
                }
                handled_providers = ChainWalletStamp.objects.filter(
                    chain_id=1, address=address, provider__in=deleted_providers
                ).values_list("provider", flat=True)
                # A delete against the legacy fallback needs scoped history so
                # a late write from an older client does not revive that stamp.
                replacements.extend(
                    ChainWalletStamp(
                        chain_id=1,
                        address=address,
                        provider=provider,
                        stamp={},
                        proof_value="",
                        deleted_at=deleted_at,
                    )
                    for provider in deleted_providers.difference(handled_providers)
                )
                # A scoped edit also supersedes its exact mainnet legacy stamp.
                # Keep the legacy record and proof for revocation checks.
                CeramicCache.objects.filter(
                    address=address,
                    provider__in=providers,
                    deleted_at__isnull=True,
                    stamp__credentialSubject__id__iexact=did,
                ).alias(
                    subject_provider=KT("stamp__credentialSubject__provider")
                ).filter(
                    subject_provider=F("provider")
                ).update(
                    deleted_at=deleted_at
                )
            ChainWalletStamp.objects.bulk_create(replacements)
        return stamp_response(chain_id, address)


@api_router.post(
    "/wallet-stamps/score", auth=ScopedCacheAuth(), response=ChainWalletScoreResponse
)
def score_current_wallet(request, alternate_scorer_id: int | None = None):
    chain_id, address, _ = request.auth
    try:
        community = Community.objects.get(
            pk=alternate_scorer_id or settings.CERAMIC_CACHE_SCORER_ID
        )
    except Community.DoesNotExist as exc:
        raise NotFoundApiException("No scorer matches the given criteria") from exc
    return async_to_sync(score_chain_wallet)(address, chain_id, community)
