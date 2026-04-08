"""Wallet group linking/unlinking API endpoints."""

from typing import List

from django.conf import settings
from django.db import transaction
from eth_account import Account as EthAccount
from eth_account.messages import encode_defunct
from ninja import Router, Schema
from ninja.errors import HttpError
from web3 import Web3

import api_logging as logging
from account.models import (
    Nonce,
    WalletGroup,
    WalletGroupCommunityClaim,
    WalletGroupMembership,
)
from account.siwe_validation import validate_siwe_domain, validate_siwe_expiration

log = logging.getLogger(__name__)

MAX_GROUP_SIZE = 10

router = Router()


class SiwePayload(Schema):
    """SIWE message + signature pair. Identical to account.api.SiweVerifySubmit
    but defined locally to avoid a circular import."""

    message: dict
    signature: str


class LinkWalletsPayload(Schema):
    wallet_a: SiwePayload
    wallet_b: SiwePayload


class WalletGroupResponse(Schema):
    group_id: int
    addresses: List[str]


def verify_siwe_ownership(payload: SiwePayload) -> str:
    """Verify SIWE message+signature, return lowercase address.

    Simplified verification that validates nonce and recovers the signer address
    via ecrecover (EOA wallets). Raises HttpError on failure.
    """
    address_raw = payload.message.get("address", "")
    nonce = payload.message.get("nonce")

    if not address_raw or not nonce:
        raise HttpError(400, "Missing address or nonce in SIWE message")

    # Validate domain against allowlist
    message_domain = payload.message.get("domain")
    if not validate_siwe_domain(message_domain, settings.SIWE_ALLOWED_DOMAINS_ACCOUNT):
        raise HttpError(400, "Invalid domain in SIWE message")

    # Validate expiration
    if not validate_siwe_expiration(payload.message.get("expirationTime")):
        raise HttpError(400, "SIWE message has expired")

    try:
        address = Web3.to_checksum_address(address_raw)
    except ValueError:
        raise HttpError(400, "Invalid address format")

    # Validate and consume nonce
    if not Nonce.use_nonce(nonce):
        raise HttpError(400, "Invalid or expired nonce")

    # Reconstruct SIWE message text for signature verification
    from siwe import SiweMessage

    siwe_message_dict = {
        "domain": payload.message.get("domain"),
        "address": address,
        "statement": payload.message.get("statement"),
        "uri": payload.message.get("uri"),
        "version": payload.message.get("version"),
        "chain_id": payload.message.get("chainId", 1),
        "nonce": nonce,
        "issued_at": payload.message.get("issuedAt"),
    }
    if payload.message.get("expirationTime"):
        siwe_message_dict["expiration_time"] = payload.message["expirationTime"]

    siwe_msg = SiweMessage(**siwe_message_dict)
    message_text = siwe_msg.prepare_message()

    prefixed_message = encode_defunct(text=message_text)
    try:
        recovered = EthAccount.recover_message(
            prefixed_message, signature=payload.signature
        )
        if recovered.lower() != address.lower():
            raise HttpError(401, "Signature verification failed")
    except HttpError:
        raise
    except Exception:
        raise HttpError(401, "Signature verification failed")

    return address.lower()


@router.post("/link", response=WalletGroupResponse)
def link_wallets(request, payload: LinkWalletsPayload):
    """Link two wallets together.

    Both wallets must prove ownership via SIWE signatures.
    - If neither is in a group → creates a new group with both.
    - If wallet_a is already in a group → adds wallet_b to it.
    - wallet_b must not already be in a group.
    - Both wallets in groups (different or same) → error.
    """
    address_a = verify_siwe_ownership(payload.wallet_a)
    address_b = verify_siwe_ownership(payload.wallet_b)

    if address_a == address_b:
        raise HttpError(400, "Cannot link a wallet to itself")

    with transaction.atomic():
        # Lock both rows to prevent races
        memberships = {
            m.address: m
            for m in WalletGroupMembership.objects.select_for_update().filter(
                address__in=[address_a, address_b]
            )
        }

        a_membership = memberships.get(address_a)
        b_membership = memberships.get(address_b)

        if b_membership:
            raise HttpError(400, "wallet_b is already in a group")

        if a_membership:
            # Add wallet_b to wallet_a's existing group
            group = a_membership.group
            current_size = WalletGroupMembership.objects.filter(group=group).count()
            if current_size >= MAX_GROUP_SIZE:
                raise HttpError(
                    400, f"Wallet group cannot exceed {MAX_GROUP_SIZE} members"
                )
            WalletGroupMembership.objects.create(group=group, address=address_b)
        else:
            # Neither in a group — create new group with both
            group = WalletGroup.objects.create()
            WalletGroupMembership.objects.create(group=group, address=address_a)
            WalletGroupMembership.objects.create(group=group, address=address_b)

        addresses = list(
            WalletGroupMembership.objects.filter(group=group).values_list(
                "address", flat=True
            )
        )

    return WalletGroupResponse(group_id=group.id, addresses=addresses)


def _invalidate_scores_for_claims(claims):
    """Bulk-invalidate scores for a set of canonical claims."""
    from django.db.models import Q

    from registry.models import Score

    conditions = Q()
    for claim in claims:
        conditions |= Q(
            passport__address=claim.canonical_address,
            passport__community=claim.community,
        )
    if conditions:
        Score.objects.filter(conditions).update(
            status=Score.Status.PROCESSING,
            stamps=None,
            stamp_scores=None,
            evidence=None,
        )


@router.post("/unlink", response={200: dict, 404: dict})
def unlink_wallet(request, payload: SiwePayload):
    """Remove a wallet from its group.

    Requires SIWE proof from the wallet being removed.
    If the group would have only 1 member left, the group is deleted.
    Canonical claims for this address are also deleted.
    """
    address = verify_siwe_ownership(payload)

    with transaction.atomic():
        try:
            membership = WalletGroupMembership.objects.select_for_update().get(
                address=address
            )
        except WalletGroupMembership.DoesNotExist:
            raise HttpError(404, "Wallet is not in a group")

        group = membership.group

        # Invalidate canonical scores where this address is canonical
        canonical_claims = list(
            WalletGroupCommunityClaim.objects.filter(
                group=group, canonical_address=address
            )
        )
        _invalidate_scores_for_claims(canonical_claims)
        WalletGroupCommunityClaim.objects.filter(
            group=group, canonical_address=address
        ).delete()

        # Remove from group
        membership.delete()

        # If only 1 member left, delete the group entirely
        remaining = WalletGroupMembership.objects.filter(group=group).count()
        if remaining <= 1:
            remaining_claims = list(
                WalletGroupCommunityClaim.objects.filter(group=group)
            )
            _invalidate_scores_for_claims(remaining_claims)
            WalletGroupMembership.objects.filter(group=group).delete()
            WalletGroupCommunityClaim.objects.filter(group=group).delete()
            group.delete()

    return {"success": True}


@router.get("/{address}", response={200: WalletGroupResponse, 404: dict})
def get_wallet_group(request, address: str):
    """Get wallet group info for an address."""
    address_lower = address.lower()
    try:
        membership = WalletGroupMembership.objects.get(address=address_lower)
    except WalletGroupMembership.DoesNotExist:
        raise HttpError(404, "Wallet is not in a group")

    addresses = list(
        WalletGroupMembership.objects.filter(group=membership.group).values_list(
            "address", flat=True
        )
    )
    return WalletGroupResponse(group_id=membership.group_id, addresses=addresses)
