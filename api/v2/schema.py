from datetime import datetime
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from ninja import Schema
from pydantic import (
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from typing_extensions import Self

from registry.api.schema import Passport, StatusEnum, ThresholdScoreEvidenceResponse


class V2ScoreResponse(Schema):
    address: str
    score: Optional[Decimal]
    passing_score: bool
    last_score_timestamp: Optional[str]
    expiration_timestamp: Optional[str]
    threshold: Decimal
    error: Optional[str]
    stamps: Optional[Dict[str, Dict]]


class DetailedScoreResponseV2(Schema):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    address: str | None = None
    score: Optional[str | Decimal]
    status: Optional[StatusEnum]
    last_score_timestamp: Optional[str | datetime]
    expiration_date: Optional[str | datetime]
    evidence: Optional[ThresholdScoreEvidenceResponse]
    error: Optional[str]
    stamps: Optional[Dict] = {}
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

    @field_validator("stamps", mode="before")
    @classmethod
    def validate_stamps(cls, v: Any):
        if v is None:
            return {}
        return v
