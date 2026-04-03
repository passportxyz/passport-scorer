"""Wallet group linking/unlinking API endpoints."""

import api_logging as logging
from django.conf import settings
from eth_account import Account as EthAccount
from eth_account.messages import encode_defunct
from ninja import Router, Schema
from ninja.errors import HttpError
from typing import List, Optional
from web3 import Web3

from account.models import (
    Nonce,
    WalletGroup,
    WalletGroupCommunityClaim,
    WalletGroupMembership,
)

log = logging.getLogger(__name__)

router = Router()


class SiwePayload(Schema):
    message: dict
    signature: str


class LinkWalletsPayload(Schema):
    wallet_a: SiwePayload
    wallet_b: SiwePayload


class AddWalletPayload(Schema):
    existing_member: SiwePayload
    new_wallet: SiwePayload


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
    """Link two wallets into a new wallet group.

    Both wallets must prove ownership via SIWE signatures.
    Neither wallet can already be in a group.
    """
    address_a = verify_siwe_ownership(payload.wallet_a)
    address_b = verify_siwe_ownership(payload.wallet_b)

    if address_a == address_b:
        raise HttpError(400, "Cannot link a wallet to itself")

    # Check neither is already in a group
    existing = WalletGroupMembership.objects.filter(
        address__in=[address_a, address_b]
    )
    if existing.exists():
        raise HttpError(400, "One or both wallets are already in a group")

    # Create group with both members
    group = WalletGroup.objects.create()
    WalletGroupMembership.objects.create(group=group, address=address_a)
    WalletGroupMembership.objects.create(group=group, address=address_b)

    return WalletGroupResponse(
        group_id=group.id, addresses=[address_a, address_b]
    )


@router.post("/add", response=WalletGroupResponse)
def add_wallet(request, payload: AddWalletPayload):
    """Add a new wallet to an existing group.

    Requires SIWE proof from an existing member and from the new wallet.
    """
    existing_address = verify_siwe_ownership(payload.existing_member)
    new_address = verify_siwe_ownership(payload.new_wallet)

    if existing_address == new_address:
        raise HttpError(400, "Cannot add a wallet to its own group")

    # Verify existing member is in a group
    try:
        membership = WalletGroupMembership.objects.get(address=existing_address)
    except WalletGroupMembership.DoesNotExist:
        raise HttpError(404, "Existing member is not in a wallet group")

    # Check new wallet isn't already in a group
    if WalletGroupMembership.objects.filter(address=new_address).exists():
        raise HttpError(400, "New wallet is already in a group")

    WalletGroupMembership.objects.create(
        group=membership.group, address=new_address
    )

    addresses = list(
        WalletGroupMembership.objects.filter(
            group=membership.group
        ).values_list("address", flat=True)
    )
    return WalletGroupResponse(group_id=membership.group_id, addresses=addresses)


@router.post("/unlink", response={200: dict, 404: dict})
def unlink_wallet(request, payload: SiwePayload):
    """Remove a wallet from its group.

    Requires SIWE proof from the wallet being removed.
    If the group would have only 1 member left, the group is deleted.
    Canonical claims for this address are also deleted.
    """
    address = verify_siwe_ownership(payload)

    try:
        membership = WalletGroupMembership.objects.get(address=address)
    except WalletGroupMembership.DoesNotExist:
        raise HttpError(404, "Wallet is not in a group")

    group = membership.group

    # Delete canonical claims where this address is canonical
    WalletGroupCommunityClaim.objects.filter(
        group=group, canonical_address=address
    ).delete()

    # Remove from group
    membership.delete()

    # If only 1 member left, delete the group entirely
    remaining = WalletGroupMembership.objects.filter(group=group).count()
    if remaining <= 1:
        # Delete remaining memberships and all claims
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
        WalletGroupMembership.objects.filter(
            group=membership.group
        ).values_list("address", flat=True)
    )
    return WalletGroupResponse(
        group_id=membership.group_id, addresses=addresses
    )
