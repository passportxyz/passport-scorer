"""Linkage source for wallet grouping.

Resolves the set of wallets linked to a given address by querying the Silk
auth-server's public read endpoint, behind a short SWR cache and a killswitch.
Phase 3b of the wallet-linking → Silk migration (holonym-foundation/internal-docs#1058).

The single ``get_linked_addresses`` coroutine is the only public API. Callers
should ``await`` it and treat the returned list as "all addresses to score for
this user, including the requested address." Ordering is not guaranteed by
callers; the canonical-wallet decision lives downstream in the scoring code path.

Operational behaviour:
- ``LINKED_WALLETS_SOURCE_ENABLED`` killswitch: when false/unset, skip the Silk
  call entirely and return the solo set.
- 60s freshness cache on the success path; an empty Silk response (no linkage)
  is cached too (negative caching) so most addresses don't thunder the endpoint.
- On any Silk failure we never poison the cache; we serve the last good value if
  we have one, otherwise fall back to the solo set.
"""

from __future__ import annotations

import logging

import aiohttp
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Freshness window for a successful lookup. Within this many seconds we serve the
# cached value without calling Silk.
CACHE_TTL = 60
# How long the "last good" value survives for stale-on-failure fallback. Outlives
# the freshness window so an outage after the 60s lapse can still serve stale data.
LAST_GOOD_TTL = 60 * 60
# Per-request Silk timeout (seconds). Scoring is latency-sensitive; fail fast.
REQUEST_TIMEOUT = 2.0

FRESH_KEY = "linked_wallets:v1:{}"
LAST_GOOD_KEY = "linked_wallets:lastgood:{}"


async def get_linked_addresses(address: str) -> list[str]:
    """Return all addresses linked to ``address`` (always lowercased).

    Returns ``[address]`` when the killswitch is off, when Silk reports no
    linkage, or when Silk is unreachable and no cached value exists.
    """
    address = address.lower()

    if not getattr(settings, "LINKED_WALLETS_SOURCE_ENABLED", False):
        return [address]

    fresh_key = FRESH_KEY.format(address)
    cached = await cache.aget(fresh_key)
    if cached is not None:
        return cached

    try:
        raw_addresses = await _fetch_from_silk(address)
    except Exception as exc:
        # Outage: never poison the cache. Serve the last good value if present,
        # else fall back to solo.
        last_good = await cache.aget(LAST_GOOD_KEY.format(address))
        if last_good is not None:
            logger.warning(
                "linked wallets: Silk fetch failed for %s, serving stale value (%s)",
                address,
                exc,
            )
            return last_good
        logger.warning(
            "linked wallets: Silk fetch failed for %s with no cached value, "
            "falling back to solo (%s)",
            address,
            exc,
        )
        return [address]

    linked = _normalize(raw_addresses, address)
    # Success path: refresh both the freshness key and the longer-lived last-good
    # key. Empty Silk responses normalize to the solo set and are cached too.
    await cache.aset(fresh_key, linked, CACHE_TTL)
    await cache.aset(LAST_GOOD_KEY.format(address), linked, LAST_GOOD_TTL)
    return linked


async def _fetch_from_silk(address: str) -> list[str]:
    """GET the linked-wallet cluster for ``address`` from the Silk auth-server.

    Raises on any non-2xx response or transport error so the caller can apply its
    fallback policy. Returns the raw ``addresses`` list (possibly empty).
    """
    url = (
        f"{settings.SILK_AUTH_SERVER_URL}"
        f"/api/public/linked-wallets/by-address/{address}"
    )
    headers = {"X-Service-Key": settings.SILK_SERVICE_API_KEY}
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            body = await response.json()

    return body.get("addresses", [])


def _normalize(addresses: list[str], address: str) -> list[str]:
    """Lowercase, dedupe, guarantee ``address`` is present, and sort lexically."""
    cluster = {addr.lower() for addr in addresses}
    cluster.add(address)
    return sorted(cluster)
