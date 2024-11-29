"""Internal API Schema"""

from datetime import datetime
from typing import List, Optional

from ninja_schema import Schema

from ceramic_cache.models import BanType


class CredentialSubject(Schema):
    hash: Optional[str]
    provider: Optional[str]
    id: Optional[str]


class Credential(Schema):
    credentialSubject: CredentialSubject


class CheckBanResult(Schema):
    hash: str
    is_banned: bool
    end_time: datetime | None = None
    ban_type: BanType | None = None
    reason: str | None = None


class RevocationCheckPayload(Schema):
    proof_values: List[str]


class RevocationCheckResponse(Schema):
    proof_value: str
    is_revoked: bool
