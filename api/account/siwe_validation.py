import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def validate_siwe_domain(domain: str | None, allowed_domains: list[str]) -> bool:
    """Validate SIWE message domain against allowlist. Case-insensitive."""
    if not domain:
        return False
    return domain.lower() in {d.lower() for d in allowed_domains}


def validate_siwe_expiration(expiration_time: str | None) -> bool:
    """Check that SIWE message has not expired. Returns True if valid (not expired or no expiration set)."""
    if expiration_time is None:
        return True  # No expiration set = no check (nonce TTL provides time-bounding)
    if not expiration_time:
        return False  # Empty string is invalid
    try:
        exp = datetime.fromisoformat(
            expiration_time
        )  # Python 3.11+ handles "Z" natively
        return datetime.now(timezone.utc) < exp
    except (ValueError, TypeError):
        return False
