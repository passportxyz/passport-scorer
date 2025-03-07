"""
This module loads the configured issuers and the start times when each issuer becomes active.

IAM_JWK_EIP712_V1_ISSUER=did:ethr:0x1234567890abcdef
IAM_JWK_EIP712_V1_START_TIME=2021-01-01T00:00:00Z

IAM_JWK_EIP712_V2_ISSUER=did:ethr:0x1234567890abcdef
IAM_JWK_EIP712_V2_START_TIME=2021-04-01T00:00:00Z

IAM_JWK_EIP712_V3_ISSUER=did:ethr:0x1234567890abcdef
IAM_JWK_EIP712_V3_START_TIME=2021-07-01T00:00:00Z

"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import List

from django.conf import settings
from pydantic import BaseModel

log = logging.getLogger(__name__)


class IssuerVersion(BaseModel):
    version: str
    issuer: str
    start_time: datetime


KEY_ENV_PREFIX = "IAM_JWK_EIP712_V"
pattern = KEY_ENV_PREFIX + r"(?P<version>\d+)_ISSUER"


def get_versions() -> List[int]:
    ret: List[int] = []
    for env_key in os.environ.keys():
        match = re.match(pattern, env_key)
        if match:
            version = int(match.group("version"))
            if version > 0:
                ret.append(version)

    return ret


def load_issuer_from_env(version: int) -> IssuerVersion:
    try:
        return IssuerVersion(
            version=str(version),
            issuer=os.getenv(f"{KEY_ENV_PREFIX}{version}_ISSUER"),
            start_time=datetime.fromisoformat(
                os.getenv(f"{KEY_ENV_PREFIX}{version}_START_TIME")
            ),
        )
    except Exception as e:
        log.error(
            "Error loading issuer from env for version {%s}: {%s}",
            version,
            e,
            exc_info=True,
        )
        raise


def load_issuer_versions() -> List[IssuerVersion]:
    now = datetime.now(timezone.utc)
    issuer_versions: List[IssuerVersion] = []

    versions = get_versions()

    for version in versions:
        issuer_version = load_issuer_from_env(version)
        issuer_versions.append(issuer_version)

    for issuer in settings.TRUSTED_IAM_ISSUERS:
        # Adding support for the legacy issuer
        if issuer.startswith("did:ethr:"):
            issuer_versions.append(
                IssuerVersion(
                    version="0.0.0",
                    issuer=issuer,
                    start_time=datetime(1970, 1, 1, tzinfo=timezone.utc),
                )
            )

    issuer_versions.sort(key=lambda issuer_version: issuer_version.start_time)

    if len(issuer_versions) <= 0:
        raise Exception(
            "No issuer versions loaded. Please configure at least a `TRUSTED_IAM_ISSUERS` or IAM_JWK_EIP712_V{}_ISSUER ...."
        )

    if issuer_versions[0].start_time > now:
        raise Exception(
            "No active issuer found. Please configure at least a `TRUSTED_IAM_ISSUERS` or IAM_JWK_EIP712_V{}_ISSUER ... with starttime in the past"
        )

    return issuer_versions


NUM_ISSUERS_TO_TRUST = 2


def get_current_trusted_issuer_versions() -> list[IssuerVersion]:
    """
    We will always trust the current and previous issuers setups
    """
    now = datetime.now(timezone.utc)
    issuer_version_list = get_loaded_versions()
    issuers_to_trust = [issuer_version_list[0]]

    for issuer_version in issuer_version_list[1:]:
        if issuer_version.start_time > now:
            return issuers_to_trust
        else:
            if len(issuers_to_trust) >= NUM_ISSUERS_TO_TRUST:
                issuers_to_trust.pop(0)
            issuers_to_trust.append(issuer_version)

    # This should contain the legacy issuer only in this
    return issuers_to_trust


def get_current_trusted_issuers() -> list[str]:
    """
    Return the list of issuers (returns the did only)
    """
    return [iv.issuer for iv in get_current_trusted_issuer_versions()]


def get_loaded_versions() -> list[IssuerVersion]:
    try:
        global LOADED_ISSUER_VERSIONS
        if LOADED_ISSUER_VERSIONS is None:
            LOADED_ISSUER_VERSIONS = load_issuer_versions()
            log.info("Loaded issuer versions: %s", LOADED_ISSUER_VERSIONS)
        return LOADED_ISSUER_VERSIONS
    except Exception as e:
        log.error("Error loading issuer versions: {%s}", e, exc_info=True)
        raise


# List of issuer versions sorted by start time
LOADED_ISSUER_VERSIONS = None
