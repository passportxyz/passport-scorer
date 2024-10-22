from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

# todo
from ninja import Schema
from pydantic import ConfigDict, Field, computed_field, field_validator, model_validator
from typing_extensions import Self

from registry.models import Event, Passport, Score


class SubmitPassportPayload(Schema):
    address: str
    community: str = "Deprecated"
    scorer_id: str | None = ""
    signature: str = ""
    nonce: str = ""

    @field_validator("community", mode="before")
    @classmethod
    def validate_community(cls, v: Any):
        return str(v)

    @field_validator("scorer_id", mode="before")
    @classmethod
    def validate_scorer_id(cls, v: Any):
        return str(v)


class ScoreEvidenceResponse(Schema):
    type: str
    success: bool


class ThresholdScoreEvidenceResponse(ScoreEvidenceResponse):
    rawScore: float
    threshold: float


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
    metadata: Optional[StampCredentialResponseMetadata] = None


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
    model_config = ConfigDict(arbitrary_types_allowed=True)
    address: str | None = None
    score: Optional[str | Decimal]
    status: Optional[StatusEnum]
    last_score_timestamp: Optional[str | datetime]
    expiration_date: Optional[str | datetime]
    evidence: Optional[ThresholdScoreEvidenceResponse]
    error: Optional[str]
    stamp_scores: Optional[Dict] = {}
    passport: Optional[Passport] = Field(exclude=True, default=None)

    @model_validator(mode="after")
    def check_address(self) -> Self:
        if self.passport and self.address is None:
            self.address = self.passport.address
        return self

    @field_validator("last_score_timestamp", mode="before")
    @classmethod
    def validate_last_score_timestamp(cls, v: Any, values: Dict):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    @field_validator("expiration_date", mode="before")
    @classmethod
    def validate_expiration_date(cls, v: Any):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


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

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v: Any, values: Dict):
        if isinstance(v, Decimal):
            return str(v)
        return v


class GtcEventsResponse(Schema):
    results: List[LegacyStakeSchema]


class StakeSchema(Schema):
    chain: str
    staker: str
    stakee: str
    amount: str
    unlock_time: str
    lock_duration: str


class GtcStakeEventsSchema(Schema):
    address: str
    round_id: int
