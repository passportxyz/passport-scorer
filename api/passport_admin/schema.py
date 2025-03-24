from datetime import date, datetime
from typing import List, Optional

from ninja import Schema
from pydantic import field_serializer, field_validator


class GenericResponse(Schema):
    status: str


class Banner(Schema):
    content: str
    link: Optional[str] = None
    banner_id: int
    application: str = "passport"


class NotificationSchema(Schema):
    notification_id: str
    type: str
    content: str
    link: Optional[str] = None
    link_text: Optional[str] = None
    is_read: bool
    created_at: date


class NotificationResponse(Schema):
    items: List[NotificationSchema]


class ChainSchema(Schema):
    id: str
    name: str


class NotificationPayload(Schema):
    scorer_id: int
    expired_chain_ids: Optional[List[ChainSchema]] = None


class DismissPayload(Schema):
    dismissal_type: str


class ServerStatusResponse(Schema):
    timestamp: datetime | str | None
    success: int
    failed: int
    total: int
    status: Optional[str] = None
    age: Optional[float] = None

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.isoformat() if timestamp is not None else "null"

    @field_validator("timestamp", mode="before")
    @classmethod
    def handle_timestamp(cls, value: datetime | str | None) -> datetime | None:
        print(" =" * 40)
        print(" ====> value", value, type(vaue))
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return datetime
