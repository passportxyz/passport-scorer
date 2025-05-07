import hashlib

import dag_cbor
from django.utils import timezone

from account.models import Community
from ceramic_cache.api.v1 import handle_get_scorer_weights
from ceramic_cache.models import CeramicCache
from passport_admin.models import Notification


def generate_stamp_expired_notifications(address, community: Community):
    """
    Generate stamp expired notifications for a specific address
    """
    current_date = timezone.now()

    ceramic_cache = CeramicCache.objects.filter(
        address=address, deleted_at__isnull=True, expiration_date__lt=current_date
    )

    # Get all notification to which user has not yet reacted
    existing_notifications_with_no_status = Notification.objects.filter(
        type="stamp_expiry",
        is_active=True,
        eth_address=address,
        notificationstatus__isnull=True,
    )
    existing_notifications_by_id = {
        n.notification_id: n for n in existing_notifications_with_no_status
    }

    weights = handle_get_scorer_weights(community.id)
    notifications_to_create = []
    for cc in ceramic_cache:
        # Ideally we would move this filtering to the UI ...
        stamp_weight = weights.get(cc.provider)
        if stamp_weight and float(stamp_weight) > 0:
            cs = cc.stamp["credentialSubject"]
            stamp_hash = cs["hash"] if "hash" in cs else cs["nullifiers"][0]
            encoded_data = dag_cbor.encode(
                {
                    "cc_id": cc.id,
                    "cc_provider": cc.provider,
                    "cc_stamp_hash": stamp_hash,
                    "cc_stamp_id": cc.stamp["credentialSubject"]["id"],
                    "cc_stamp_proof": cc.proof_value,
                    "address": address,
                }
            )
            notification_id = hashlib.sha256(encoded_data).hexdigest()

            notification_exists = Notification.objects.filter(
                notification_id=notification_id
            ).exists()

            if not notification_exists:
                notifications_to_create.append(
                    Notification(
                        notification_id=notification_id,
                        type="stamp_expiry",
                        is_active=True,
                        content=f"Your {cc.provider} stamp has expired. Please reverify to keep your Passport up to date.",
                        link=cc.provider,
                        eth_address=address,
                    )
                )
            else:
                if notification_id in existing_notifications_by_id:
                    del existing_notifications_by_id[notification_id]

    # Create the notifications in bulk
    Notification.objects.bulk_create(notifications_to_create)

    # Invalidate existing notifications that are still in existing_notifications_by_id,
    # the user has refreshed the stamp
    for _, notification in existing_notifications_by_id.items():
        notification.delete()
