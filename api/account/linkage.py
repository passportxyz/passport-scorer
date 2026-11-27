"""Linkage source for wallet grouping.

Phase 0 stub: solo set only. Phase 3b (#589) replaces with Silk fetch +
SWR cache + ``LINKED_WALLETS_SOURCE_ENABLED`` killswitch +
``scorer.linked_wallets.fallback_to_solo`` metric.

Callers should ``await get_linked_addresses`` and treat the returned list as
"all addresses to score for
this user, including the requested address." Ordering is not guaranteed; the
canonical-wallet decision lives downstream in the scoring code path.
"""

from __future__ import annotations

import os

import aiohttp


async def get_linked_addresses(address: str) -> list[str]:
    """Return all addresses linked to ``address``.

    Phase 0 stub: returns just the solo address. Phase 3b will replace the
    body with a Silk HTTP fetch + SWR cache + killswitch fallback.

    The signature is intentionally async to mirror Phase 3b's HTTP fetch.
    """
    return [address.lower()]


async def is_linked_contract_wallet(chain_id: int, address: str) -> bool:
    """Check Silk's active link using the exact contract wallet identity."""
    origin = os.environ.get("SILK_AUTH_SERVER_URL")
    service_key = os.environ.get("SILK_SERVICE_API_KEY")
    if (
        os.environ.get("CHAIN_WALLET_SCORING_ENABLED") != "true"
        or not origin
        or not service_key
    ):
        raise RuntimeError("Silk linkage is not configured")
    url = f"{origin.rstrip('/')}/api/public/linked-wallets/by-identity/{address}"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        async with session.get(
            url,
            params={"chainId": str(chain_id)},
            headers={"X-Service-Key": service_key},
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise RuntimeError("Silk linkage request failed")
            payload = await response.json()
    return any(
        type(member.get("chainId")) is int
        and member["chainId"] == chain_id
        and member.get("address") == address
        for member in payload["wallets"]
    )
