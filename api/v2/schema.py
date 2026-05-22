from decimal import Decimal
from typing import (
    Dict,
    Optional,
)

from ninja import Schema
from pydantic import field_serializer, model_serializer


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
