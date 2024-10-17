from typing import Dict, Optional

from ninja import Schema


class V2ScoreResponse(Schema):
    address: str
    score: Optional[str]
    passing_score: bool
    last_score_timestamp: Optional[str]
    expiration_timestamp: Optional[str]
    threshold: str
    error: Optional[str]
    stamp_scores: Optional[Dict[str, str]]
