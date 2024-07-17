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
    current_date = timezone.now().date()

    ceramic_cache = CeramicCache.objects.filter(
        address=address, deleted_at__isnull=True, expiration_date__lt=current_date
    )

    weights = handle_get_scorer_weights(community.id)

    for cc in ceramic_cache:
        stamp_weight = weights.get(cc.provider)
        if stamp_weight and float(stamp_weight) > 0:
            encoded_data = dag_cbor.encode(
                {
                    "cc_id": cc.id,
                    "cc_provider": cc.provider,
                    "cc_stamp_hash": cc.stamp["credentialSubject"]["hash"],
                    "cc_stamp_id": cc.stamp["credentialSubject"]["id"],
                    "address": address,
                }
            )
            notification_id = hashlib.sha256(encoded_data).hexdigest()

            notification_exists = Notification.objects.filter(
                notification_id=notification_id
            ).exists()

            if not notification_exists:
                Notification.objects.create(
                    notification_id=notification_id,
                    type="stamp_expiry",
                    is_active=True,
                    content=f"Your {cc.provider} stamp has expired. Please reverify to keep your Passport up to date.",
                    link=cc.provider,
                    eth_address=address,
                )
