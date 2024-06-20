from ninja import Schema
from typing import List, Optional


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
    title: str
    content: str


class NotificationResponse(Schema):
    items: List[NotificationSchema]


class ChainSchema(Schema):
    id: str
    name: str


class NotificationPayload(Schema):
    expired_chain_ids: Optional[List[ChainSchema]] = None


class DismissPayload(Schema):
    dismissal_type: bool
