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
import re
from dataclasses import dataclass

import aiohttp


async def get_linked_addresses(address: str) -> list[str]:
    """Return all addresses linked to ``address``.

    Phase 0 stub: returns just the solo address. Phase 3b will replace the
    body with a Silk HTTP fetch + SWR cache + killswitch fallback.

    The signature is intentionally async to mirror Phase 3b's HTTP fetch.
    """
    return [address.lower()]


@dataclass(frozen=True)
class WalletIdentity:
    address: str
    chain_id: int | None = None

    @property
    def key(self) -> str:
        if self.chain_id is None:
            return self.address
        return f"eip155:{self.chain_id}:{self.address}"


@dataclass(frozen=True)
class WalletCluster:
    canonical: WalletIdentity
    wallets: tuple[WalletIdentity, ...]


def chain_wallet_scoring_enabled() -> bool:
    return os.environ.get("CHAIN_WALLET_SCORING_ENABLED") == "true"


async def get_wallet_cluster(wallet: WalletIdentity) -> WalletCluster | None:
    if not chain_wallet_scoring_enabled():
        return None
    origin = os.environ.get("SILK_AUTH_SERVER_URL")
    service_key = os.environ.get("SILK_SERVICE_API_KEY")
    if not origin or not service_key:
        raise RuntimeError("Silk linkage is not configured")
    url = f"{origin.rstrip('/')}/api/public/linked-wallets/by-identity/{wallet.address}"
    params = {"chainId": str(wallet.chain_id)} if wallet.chain_id is not None else {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        async with session.get(
            url,
            params=params,
            headers={"X-Service-Key": service_key},
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                raise RuntimeError("Silk linkage request failed")
            payload = await response.json()
    wallets = set()
    for member in payload["wallets"]:
        address = member["address"]
        chain_id = member.get("chainId")
        if not re.fullmatch(r"0x[0-9a-f]{40}", address) or address == "0x" + "0" * 40:
            raise RuntimeError("Invalid linked wallet address")
        if chain_id is not None and (
            type(chain_id) is not int or not 0 < chain_id <= 9007199254740991
        ):
            raise RuntimeError("Invalid linked wallet chain")
        wallets.add(WalletIdentity(address, chain_id))
    canonical = WalletIdentity(payload["waapAddress"])
    if wallet not in wallets or canonical not in wallets:
        return None
    return WalletCluster(
        canonical, tuple(sorted(wallets, key=lambda identity: identity.key))
    )
