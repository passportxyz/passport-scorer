import json
from typing import List, Optional

from ceramic_cache.api.v1 import JWTDidAuth
from django.db.models import Subquery
from ninja import Router, Schema

from .models import (
    DismissedBanners,
    PassportBanner,
    Notification,
    DismissedNotification,
)
from django.utils import timezone

router = Router()


def get_address(did: str):
    start = did.index("0x")
    return did[start:]


class Banner(Schema):
    content: str
    link: Optional[str] = None
    banner_id: int
    application: str = "passport"


@router.get(
    "/banners",
    response=List[Banner],
    auth=JWTDidAuth(),
)
def get_banners(request, application: Optional[str] = "passport"):
    """
    Get all banners
    By default, it will return all banners for the Passport application.
    """
    try:
        address = get_address(request.auth.did)
        banners = (
            PassportBanner.objects.filter(is_active=True, application=application)
            .exclude(
                pk__in=Subquery(
                    DismissedBanners.objects.filter(address=address).values("banner_id")
                )
            )
            .all()
        )

        return [
            Banner(
                content=b.content,
                link=b.link,
                banner_id=b.pk,
                application=b.application,
            )
            for b in banners
        ]
    except:
        return {
            "status": "failed",
        }


class GenericResponse(Schema):
    status: str


@router.post(
    "/banners/{banner_id}/dismiss",
    response={200: GenericResponse},
    auth=JWTDidAuth(),
)
def dismiss_banner(request, banner_id: int):
    """
    Dismiss a banner
    """
    try:
        banner = PassportBanner.objects.get(id=banner_id)
        address = get_address(request.auth.did)
        DismissedBanners.objects.create(address=address, banner=banner)
        return {
            "status": "success",
        }
    except PassportBanner.DoesNotExist:
        return {
            "status": "failed",
        }


class NotificationResponse(Schema):
    notification_id: int
    type: str
    title: str
    content: str


class NotificationSchema(Schema):
    items: List[NotificationResponse]


@router.post(
    "/notifications",
    response=NotificationSchema,
    auth=JWTDidAuth(),
)
def get_notifications(request):
    """
    Get all notifications for a specific address.
    This also includes the generic notifications
    """
    try:
        address = "0x1"  # get_address(request.auth.did)
        current_date = timezone.now().date()

        # TODO: verify payload here for onchain passport expiry notifications
        # Events.objects.filter(
        #     address=address, action=Event.Action.LIFO_DEDUPLICATION
        # ).all()
        # TODO: generate stamp expiry notifications
        # CeramicCache.objects.filter(
        #     address=address, type=CeramicCache.StampType.V1, deleted_at__isnull=True
        # ) -> filter by expiration date

        # TODO: check for deduplication events

        notifications = Notification.objects.filter(
            is_active=True, eth_address=address, expires__gte=current_date
        ).all()
        general_notifications = Notification.objects.filter(
            is_active=True, eth_address="", expires__gte=current_date
        ).all()

        all_notifications = [
            NotificationSchema(
                notification_id=n.notification_id,
                type=n.type,
                title=n.title,
                content=n.content,
            ).dict()
            for n in [*notifications, *general_notifications]
        ]
        return NotificationSchema(items=all_notifications)

    except Notification.DoesNotExist:
        return {
            "status": "failed",
        }


@router.post(
    "/notifications/{notification_id}/dismiss",
    response={200: GenericResponse},
    auth=JWTDidAuth(),
)
def dismiss_notification(request, notification_id):
    """
    Dismiss a notification
    """
    try:
        address = get_address(request.auth.did)
        notification = Notification.objects.get(notification_id=notification_id)

        DismissedNotification.objects.create(address=address, notification=notification)
        return {
            "status": "success",
        }
    except Notification.DoesNotExist:
        return {
            "status": "failed",
        }
