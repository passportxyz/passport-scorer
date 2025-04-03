"""
This module contains the logic for generating deduplication notifications for a specific address.
"""

import hashlib
from datetime import timedelta

import dag_cbor
from django.utils import timezone

from account.models import Community
from ceramic_cache.api.v1 import handle_get_scorer_weights
from passport_admin.models import Notification
from registry.models import Event


def generate_deduplication_notifications(address, community: Community):
    """
    Generate deduplication notifications for a specific address.

    Args:
        address (str): The address for which to generate deduplication notifications.

    Returns:
        None
    """
    thirty_days_ago = timezone.now() - timedelta(days=30)

    deduplication_events = Event.objects.filter(
        address=address,
        action=Event.Action.LIFO_DEDUPLICATION,
        created_at__gte=thirty_days_ago,
        community=community,
    )

    weights = handle_get_scorer_weights(community.id)
    # for each deduplication event, generate a notification
    # if the notification does not already exist
    for event in deduplication_events:
        stamp_name = event.data.get("provider", "<StampName>")
        stamp_weight = weights.get(stamp_name)
        # check that stamp weight is greater than 0 which means it is an active stamp
        if stamp_weight and float(stamp_weight) > 0:
            encoded_data = dag_cbor.encode(
                {
                    "action": event.action,
                    "address": event.address,
                    "data": event.data,
                    "id": event.id,
                }
            )

            notification_id = hashlib.sha256(encoded_data).hexdigest()
            notification_exists = Notification.objects.filter(
                notification_id=notification_id
            ).exists()

            if not notification_exists:
                Notification.objects.create(
                    notification_id=notification_id,
                    type="deduplication",
                    is_active=True,
                    content=f"You have claimed the same '{stamp_name}' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet {address}. Learn more about deduplication",
                    link="https://support.passport.xyz/passport-knowledge-base/using-passport/common-questions/why-is-my-passport-score-not-adding-up",
                    link_text="here",
                    created_at=timezone.now().date(),
                    eth_address=address,
                )
