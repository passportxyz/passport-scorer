from datetime import date
from typing import List, Optional

from ninja import Schema


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
