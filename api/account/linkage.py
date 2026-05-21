"""Linkage source for wallet grouping.

Phase 0 stub: solo set only. Phase 3b (#589) replaces with Silk fetch +
SWR cache + ``LINKED_WALLETS_SOURCE_ENABLED`` killswitch +
``scorer.linked_wallets.fallback_to_solo`` metric.

The single ``get_linked_addresses`` coroutine is the only public API. Callers
should ``await`` it and treat the returned list as "all addresses to score for
this user, including the requested address." Ordering is not guaranteed; the
canonical-wallet decision lives downstream in the scoring code path.
"""

from __future__ import annotations


async def get_linked_addresses(address: str) -> list[str]:
    """Return all addresses linked to ``address``.

    Phase 0 stub: returns just the solo address. Phase 3b will replace the
    body with a Silk HTTP fetch + SWR cache + killswitch fallback.

    The signature is intentionally async to mirror Phase 3b's HTTP fetch.
    """
    return [address.lower()]
