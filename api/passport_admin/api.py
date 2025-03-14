from typing import List, Optional

from django.db import IntegrityError
from django.db.models import OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from ninja import Router

from account.models import Community
from ceramic_cache.api.v1 import JWTDidAuth
from passport_admin.notification_generators.deduplication_events import (
    generate_deduplication_notifications,
)
from passport_admin.notification_generators.expired_stamp import (
    generate_stamp_expired_notifications,
)
from passport_admin.notification_generators.on_chain_expired import (
    generate_on_chain_expired_notifications,
)
from passport_admin.schema import (
    Banner,
    DismissPayload,
    GenericResponse,
    NotificationPayload,
    NotificationResponse,
    NotificationSchema,
)

from .models import (
    DismissedBanners,
    Notification,
    NotificationStatus,
    PassportBanner,
)

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
    except PassportBanner.DoesNotExist:
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
        scorer_id = payload.scorer_id
        try:
            community = Community.objects.get(id=scorer_id)
        except Community.DoesNotExist:
            raise Exception("Scorer for provided id does not exist")

        generate_deduplication_notifications(address=address, community=community)
        generate_stamp_expired_notifications(address=address, community=community)
        if payload.expired_chain_ids:
            generate_on_chain_expired_notifications(
                address=address, expired_chains=payload.expired_chain_ids
            )

        notification_status_subquery = NotificationStatus.objects.filter(
            notification=OuterRef("pk"), eth_address=address
        ).values(
            "is_read"
        )[
            :1
        ]  # [:1] is used to limit the subquery to 1 result. There should be only 1 NotificationStatus per Notification

        custom_notifications = (
            Notification.objects.filter(
                Q(is_active=True, eth_address=address)
                & (Q(expires_at__gte=current_date) | Q(expires_at__isnull=True))
                & (
                    Q(notificationstatus__is_deleted=False)
                    | Q(notificationstatus__isnull=True)
                )
            )
            .annotate(
                is_read=Coalesce(Subquery(notification_status_subquery), Value(False))
            )
            .order_by("-created_at")
        )

        general_notifications = (
            Notification.objects.filter(
                Q(is_active=True, eth_address=None)
                & (Q(expires_at__gte=current_date) | Q(expires_at__isnull=True))
                & (
                    Q(notificationstatus__is_deleted=False)
                    | Q(notificationstatus__isnull=True)
                )
            )
            .annotate(
                is_read=Coalesce(Subquery(notification_status_subquery), Value(False))
            )
            .order_by("-created_at")
        )

        all_notifications = sorted(
            [
                NotificationSchema(
                    notification_id=n.notification_id,
                    type=n.type,
                    content=n.content,
                    link=n.link,
                    link_text=n.link_text,
                    is_read=n.is_read,
                    created_at=n.created_at,
                ).dict()
                for n in [*custom_notifications, *general_notifications]
            ],
            key=lambda x: x["created_at"],
            reverse=True,
        )[:20]  # Limit to the 20 newest notifications

        return NotificationResponse(items=all_notifications).dict()

    except Notification.DoesNotExist:
        return {
            "status": "failed",
        }


@router.delete(
    "/notifications",
    response={200: GenericResponse},
    auth=JWTDidAuth(),
)
def delete_all_notifications(request):
    """
    Delete all notifications for the authenticated user
    """
    try:
        address = get_address(request.auth.did)

        # Get all relevant notifications
        notifications = Notification.objects.filter(
            Q(is_active=True) & Q(eth_address=address)
        )

        # Get existing notification statuses
        existing_statuses = NotificationStatus.objects.filter(
            notification__in=notifications, eth_address=address
        )

        # Create a set of existing notification IDs for quick lookup
        existing_notification_ids = set(
            existing_statuses.values_list("notification_id", flat=True)
        )

        # Prepare lists for bulk operations
        statuses_to_create = []
        notification_ids_to_update = []

        for notification in notifications:
            if notification.pk in existing_notification_ids:
                notification_ids_to_update.append(notification.pk)
            else:
                statuses_to_create.append(
                    NotificationStatus(
                        eth_address=address,
                        notification=notification,
                        is_deleted=True,
                        is_read=True,
                    )
                )

        # Bulk create new status records
        if statuses_to_create:
            NotificationStatus.objects.bulk_create(statuses_to_create)

        # Bulk update existing status records
        if notification_ids_to_update:
            NotificationStatus.objects.filter(
                notification_id__in=notification_ids_to_update, eth_address=address
            ).update(is_deleted=True)

        # Update notifications to inactive
        notifications.update(is_active=False)

        return {"status": "success"}

    except Exception as e:
        print(e)
        return {
            "status": "failed",
        }


@router.post(
    "/notifications/{notification_id}",
    response={200: GenericResponse},
    auth=JWTDidAuth(),
)
def dismiss_notification(request, notification_id: str, payload: DismissPayload):
    """
    Dismiss a notification
    """
    try:
        address = get_address(request.auth.did)
        notification = Notification.objects.get(notification_id=notification_id)

        if payload.dismissal_type not in ["read", "delete"]:
            return {
                "status": "Failed! Bad dismissal type.",
            }

        try:
            notification_status, created = NotificationStatus.objects.get_or_create(
                eth_address=address, notification=notification
            )
        except IntegrityError:
            notification_status = NotificationStatus.objects.get(
                eth_address=address, notification=notification
            )

        if payload.dismissal_type == "read":
            if not notification_status.is_read:
                notification_status.is_read = True
                notification_status.save()
            return {
                "status": "success",
            }

        if payload.dismissal_type == "delete":
            if not notification_status.is_deleted:
                notification_status.is_deleted = True
                notification_status.save()
            return {
                "status": "success",
            }

    except Notification.DoesNotExist:
        return {
            "status": "failed",
        }
