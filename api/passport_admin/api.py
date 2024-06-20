from typing import List, Optional

from ceramic_cache.api.v1 import JWTDidAuth
from django.db.models import Subquery
from ninja import Router
from passport_admin.schema import (
    Banner,
    GenericResponse,
    NotificationSchema,
    NotificationResponse,
    NotificationPayload,
    DismissPayload,
)
from passport_admin.notification_generators.deduplication_events import (
    generate_deduplication_notifications,
)
from passport_admin.notification_generators.expired_stamp import (
    generate_stamp_expired_notifications,
)
from passport_admin.notification_generators.on_chain_expired import (
    generate_on_chain_expired_notifications,
)


from .models import (
    DismissedBanners,
    PassportBanner,
    Notification,
    NotificationStatus,
)
from django.utils import timezone

router = Router()


def get_address(did: str):
    start = did.index("0x")
    return did[start:]


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


@router.post(
    "/notifications",
    response=NotificationResponse,
    auth=JWTDidAuth(),
)
def get_notifications(request, payload: NotificationPayload):
    """
    Get all notifications for a specific address.
    This also includes the generic notifications
    """
    try:
        address = get_address(request.auth.did)
        current_date = timezone.now().date()

        generate_deduplication_notifications(address=address)
        generate_stamp_expired_notifications(address=address)
        if payload.expired_chain_ids:
            generate_on_chain_expired_notifications(
                address=address, expired_chains=payload.expired_chain_ids
            )

        notifications = Notification.objects.filter(
            is_active=True, eth_address=address, expires_at__gte=current_date
        ).all()
        general_notifications = Notification.objects.filter(
            is_active=True, eth_address__isnull=True, expires_at__gte=current_date
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
        return NotificationResponse(items=all_notifications).dict()

    except Notification.DoesNotExist:
        return {
            "status": "failed",
        }


# TODO: @Larisa : UI implementation is like this:
# const dismissNotification = async (
#   notification_id: string,
#   dismissalType: "delete" | "read",
#   dbAccessToken?: string
# ) => {
#   if (!dbAccessToken) return;
#   const res = await axios.patch(
#     `${process.env.NEXT_PUBLIC_SCORER_ENDPOINT}/passport-admin/notifications/${notification_id}`,
#     { dismissal_type: dismissalType },
#     {
#       headers: {
#         Authorization: `Bearer ${dbAccessToken}`,
#       },
#     }
#   );

#   return res.data;
# };


# HOW TO TREAT THIS  (Read vs Delete) ?. Once a notification is dismissed, it should not be shown again.?


@router.post(
    "/notifications/{notification_id}/dismiss",
    response={200: GenericResponse},
    auth=JWTDidAuth(),
)
# ayload: DismissPayload
def dismiss_notification(request, notification_id: str):
    """
    Dismiss a notification
    """
    try:
        # TODO: set dismissal type
        address = get_address(request.auth.did)
        notification = Notification.objects.get(notification_id=notification_id)

        NotificationStatus.objects.create(
            eth_address=address, notification=notification, dismissed=True
        )
        return {
            "status": "success",
        }
    except Notification.DoesNotExist:
        return {
            "status": "failed",
        }
