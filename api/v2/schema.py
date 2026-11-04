from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from ninja import Schema
from pydantic import Field, field_serializer, model_serializer

# Why a wallet does not pass, for partners. Most specific first.
FAIL_REASON_NO_VALID_STAMPS = "no_valid_stamps"
FAIL_REASON_STAMPS_CLAIMED_ELSEWHERE = "stamps_claimed_elsewhere"
FAIL_REASON_BELOW_THRESHOLD = "below_threshold"


def get_fail_reason(
    passing_score: bool, error: Optional[str], stamps: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Return why a wallet does not pass, or None if it passes.

    None also when scoring failed (`error` is set) or the Stamps are unknown
    (`stamps` is None, e.g. a score still processing or an old history event).
    """
    if passing_score or error or stamps is None:
        return None
    if not stamps:
        return FAIL_REASON_NO_VALID_STAMPS
    for stamp in stamps.values():
        dedup = stamp.get("dedup") if isinstance(stamp, dict) else stamp.dedup
        if dedup:
            return FAIL_REASON_STAMPS_CLAIMED_ELSEWHERE
    return FAIL_REASON_BELOW_THRESHOLD


class PointsData(Schema):
    total_points: int
    is_eligible: bool
    multiplier: int
    breakdown: Dict[str, int]


class V2StampScoreResponse(Schema):
    score: str
    dedup: bool
    expiration_date: Optional[str]
    source_wallet: Optional[str] = None

    @model_serializer(mode="wrap")
    def _omit_source_wallet_if_none(self, handler):
        data = handler(self)
        if data.get("source_wallet") is None:
            data.pop("source_wallet", None)
        return data


class LinkedScoreResponse(Schema):
    """Score data from the canonical wallet in a linked wallet group."""

    address: str
    score: Optional[Decimal]
    passing_score: bool
    last_score_timestamp: Optional[str]
    expiration_timestamp: Optional[str]
    threshold: Decimal
    stamps: Optional[Dict[str, V2StampScoreResponse]]
    wallet_stamps: Optional[Dict[str, Dict[str, V2StampScoreResponse]]] = None

    @field_serializer("score")
    def serialize_score(self, score: Decimal, _info):
        return format(score, ".5f")

    @field_serializer("threshold")
    def serialize_threshold(self, threshold: Decimal, _info):
        return format(threshold, ".5f")


class V2ScoreResponse(Schema):
    address: str
    score: Optional[Decimal]
    passing_score: bool
    last_score_timestamp: Optional[str]
    expiration_timestamp: Optional[str]
    threshold: Decimal
    error: Optional[str]
    fail_reason: Optional[str] = Field(
        default=None,
        description=(
            "Why the wallet does not pass: no_valid_stamps, "
            "stamps_claimed_elsewhere or below_threshold. "
            "Null when it passes or when error is set."
        ),
    )
    stamps: Optional[Dict[str, V2StampScoreResponse]]
    points_data: Optional[PointsData] = None
    possible_points_data: Optional[PointsData] = None
    linked_score: Optional[LinkedScoreResponse] = None

    @field_serializer("score")
    def serialize_score(self, score: Decimal, _info):
        return format(score, ".5f")

    @field_serializer("threshold")
    def serialize_threshold(self, threshold: Decimal, _info):
        return format(threshold, ".5f")
