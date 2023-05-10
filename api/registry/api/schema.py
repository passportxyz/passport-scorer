from decimal import Decimal
from enum import Enum
from typing import List, Optional

from ninja import Schema
from registry.models import Score


class SubmitPassportPayload(Schema):
    address: str
    community: str = "Deprecated"
    scorer_id: str = ""
    signature: str = ""
    nonce: str = ""


class ScoreEvidenceResponse(Schema):
    type: str
    success: bool


class ThresholdScoreEvidenceResponse(ScoreEvidenceResponse):
    rawScore: Decimal
    threshold: Decimal


class StatusEnum(str, Enum):
    processing = Score.Status.PROCESSING
    error = Score.Status.ERROR
    done = Score.Status.DONE


class StampCredentialResponse(Schema):
    version: str
    credential: dict


class CursorPaginatedStampCredentialResponse(Schema):
    next: Optional[str]
    prev: Optional[str]
    items: List[StampCredentialResponse]


class GenericCommunityResponse(Schema):
    ok: bool
    scorer_id: str
    external_scorer_id: str


class DetailedScoreResponse(Schema):
    address: str
    score: Optional[str]
    status: Optional[StatusEnum]
    last_score_timestamp: Optional[str]
    evidence: Optional[ThresholdScoreEvidenceResponse]
    error: Optional[str]

    @staticmethod
    def resolve_last_score_timestamp(obj):
        if obj.last_score_timestamp:
            return obj.last_score_timestamp.isoformat()
        return None

    @staticmethod
    def resolve_address(obj):
        return obj.passport.address


class CursorPaginatedScoreResponse(Schema):
    next: Optional[str]
    prev: Optional[str]
    items: List[DetailedScoreResponse]


class SimpleScoreResponse(Schema):
    address: str
    score: Decimal  # The score should be represented as string as it will be a decimal number


class SigningMessageResponse(Schema):
    message: str
    nonce: str


class ErrorMessageResponse(Schema):
    detail: str


class GenericCommunityPayload(Schema):
    name: str
    description: str = "Programmatically created by Allo"
    external_scorer_id: str
