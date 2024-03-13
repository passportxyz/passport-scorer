from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from ninja import Schema
from pydantic import Json
from registry.models import Event, Score


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
    bulk_processing = Score.Status.BULK_PROCESSING
    error = Score.Status.ERROR
    done = Score.Status.DONE


class StampCredentialResponseMetadataForPlatform(Schema):
    id: str
    icon: str
    name: str
    description: str
    connectMessage: str


class StampCredentialResponseMetadata(Schema):
    group: str
    platform: StampCredentialResponseMetadataForPlatform
    name: str
    description: str
    hash: str


class StampCredentialResponse(Schema):
    version: str
    credential: dict
    metadata: Optional[StampCredentialResponseMetadata]


class CursorPaginatedStampCredentialResponse(Schema):
    next: Optional[str]
    prev: Optional[str]
    items: List[StampCredentialResponse]


class GenericCommunityResponse(Schema):
    ok: bool
    scorer_id: str
    external_scorer_id: str


class ActionEnum(str, Enum):
    fifo_deduplication = (
        Event.Action.FIFO_DEDUPLICATION
    )  # DEPRECATED: this deduplication method was deprecated
    lifo_deduplication = Event.Action.LIFO_DEDUPLICATION
    trustalab_score = Event.Action.TRUSTALAB_SCORE
    score_update = Event.Action.SCORE_UPDATE


class DetailedScoreResponse(Schema):
    address: str
    score: Optional[str]
    status: Optional[StatusEnum]
    last_score_timestamp: Optional[str]
    evidence: Optional[ThresholdScoreEvidenceResponse]
    error: Optional[str]
    stamp_scores: Optional[Dict]

    @staticmethod
    def resolve_last_score_timestamp(obj):
        if obj.last_score_timestamp:
            return obj.last_score_timestamp.isoformat()
        return None

    @staticmethod
    def resolve_address(obj):
        return obj.passport.address

    @staticmethod
    def resolve_stamp_scores(obj):
        if obj.stamp_scores is None or obj.stamp_scores == "":
            return {}
        return obj.stamp_scores


class HistoricalScoreData(Schema):
    score: float
    evidence: Optional[ThresholdScoreEvidenceResponse]


class DetailedHistoricalScoreResponse(Schema):
    address: str
    action: Optional[ActionEnum]
    error: Optional[str]
    community_id: Optional[int]
    created_at: Optional[str]
    data: HistoricalScoreData


class CursorPaginatedScoreResponse(Schema):
    next: Optional[str]
    prev: Optional[str]
    items: List[DetailedScoreResponse]


class CursorPaginatedHistoricalScoreResponse(Schema):
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


class StampDisplayResponseStamp(Schema):
    name: str
    description: str
    hash: str


class StampDisplayResponseGroup(Schema):
    name: str
    stamps: List[StampDisplayResponseStamp]


class StampDisplayResponse(Schema):
    id: str
    icon: str
    name: str
    description: str
    connectMessage: str
    groups: List[StampDisplayResponseGroup]


class LegacyStakeSchema(Schema):
    id: int
    event_type: str
    round_id: int
    staker: Optional[str] = None
    address: Optional[str] = None
    amount: str
    staked: bool
    block_number: int
    tx_hash: str


class GtcEventsResponse(Schema):
    results: List[LegacyStakeSchema]


class StakeSchema(Schema):
    chain: str
    staker: str
    stakee: str
    amount: str
    unlock_time: str


class GtcStakeEventsSchema(Schema):
    address: str
    round_id: int
