"""Ceramic Cache API Schema"""

from typing import Any, Dict, List, Optional

from ninja_schema import Schema

from registry.api.v1 import DetailedScoreResponse
from v2.schema import PointsData, V2ScoreResponse

from ..models import CeramicCache


class CacheStampPayload(Schema):
    address: str | None = None
    provider: str
    stamp: Any | None = None


class DeleteStampPayload(Schema):
    address: str | None = None
    provider: str


class CachedStampResponse(Schema):
    id: int
    address: str
    provider: str
    stamp: Any


class GetStampResponse(Schema):
    success: bool
    stamps: List[CachedStampResponse]


class InternalV2ScoreResponse(V2ScoreResponse):
    """Internal score response that includes human points data when available"""

    points_data: Optional[PointsData] = None


class GetStampsWithV2ScoreResponse(GetStampResponse):
    score: V2ScoreResponse


class GetStampsWithInternalV2ScoreResponse(GetStampResponse):
    """Internal response that includes stamps and score with human points data"""

    score: InternalV2ScoreResponse


class CacaoVerifySubmit(Schema):
    issuer: str
    signatures: List[Dict]
    payload: str
    nonce: str
    cid: List[int]
    cacao: List[int]


class AccessTokenResponse(Schema):
    access: str
    intercom_user_hash: str


class ComposeDBStatusPayload(Schema):
    id: int
    compose_db_save_status: CeramicCache.ComposeDBSaveStatus
    compose_db_stream_id: Optional[str] = None


class ComporeDBStatusResponse(Schema):
    updated: List[int]


class CalcScorePayload(Schema):
    alternate_scorer_id: Optional[int]
