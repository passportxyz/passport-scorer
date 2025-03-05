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

print("\n\n")
print("=" * 80)
print(pattern)
print("=" * 80)
print("\n\n")


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


def load_issuer_versions() -> List[IssuerVersion]:
    now = datetime.now(timezone.utc)
    issuer_versions: List[IssuerVersion] = []

    versions = get_versions()

    for version in versions:
        issuer_version = load_issuer_from_env(version)
        issuer_versions.append(issuer_version)

    for issuer in settings.TRUSTED_IAM_ISSUERS:
        # Adding support for the logacy issuer
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

    current_and_upcoming_issuer_versions = []
    for idx, iv in enumerate(issuer_versions[1:]):
        if iv.start_time >= now:
            current_and_upcoming_issuer_versions = issuer_versions[idx:]
            break

    return (issuer_versions, current_and_upcoming_issuer_versions)


def get_current_trusted_issuer():
    now = datetime.now(timezone.utc)
    last_issuer_version = LOADED_ISSUER_VERSIONS[0]
    for issuer_version in LOADED_ISSUER_VERSIONS[1:]:
        if issuer_version.start_time > now:
            return last_issuer_version


# List of issuer versions sorted by start time
LOADED_ISSUER_VERSIONS, CURRENT_AND_UPCOMING_ISSUER_VERSIONS = load_issuer_versions()
CURRENT_AND_UPCOMING_VERSIONS: list[str] = [
    iv.version for iv in CURRENT_AND_UPCOMING_ISSUER_VERSIONS
]

from pprint import pprint

pprint(LOADED_ISSUER_VERSIONS)
pprint(CURRENT_AND_UPCOMING_ISSUER_VERSIONS)
