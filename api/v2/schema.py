from decimal import Decimal
from typing import Dict, Optional

from ninja import Schema


class V2ScoreResponse(Schema):
    address: str
    score: Optional[Decimal]
    passing_score: bool
    last_score_timestamp: Optional[str]
    expiration_timestamp: Optional[str]
    threshold: Decimal
    error: Optional[str]
    stamp_scores: Optional[Dict[str, Decimal]]
