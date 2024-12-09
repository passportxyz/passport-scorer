from datetime import datetime
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)

from ninja import Schema
from pydantic import field_serializer


class V2ScoreResponse(Schema):
    address: str
    score: Optional[Decimal]
    passing_score: bool
    last_score_timestamp: Optional[str]
    expiration_timestamp: Optional[str]
    threshold: Decimal
    error: Optional[str]
    stamps: Optional[Dict[str, Dict]]

    @field_serializer("score")
    def serialize_score(self, score: Decimal, _info):
        return format(score, ".5f")

    @field_serializer("threshold")
    def serialize_threshold(self, threshold: Decimal, _info):
        return format(threshold, ".5f")
