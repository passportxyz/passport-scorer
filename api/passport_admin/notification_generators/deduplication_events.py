import dag_cbor
import hashlib

from django.utils import timezone
from registry.models import Event
from passport_admin.models import Notification


def generate_deduplication_notifications(address):
    """
    Generate deduplication notifications for a specific address
    """
    deduplication_events = Event.objects.filter(
        address=address, action=Event.Action.LIFO_DEDUPLICATION
    ).all()

    if len(deduplication_events) > 0:
        # for each deduplication event, generate a notification
        # if the notification does not already exist
        for event in deduplication_events:
            encoded_data = dag_cbor.encode(
                {
                    "action": event.action,
                    "address": event.address,
                    "community": event.community,
                    "data": event.data,
                    "created_at": event.created_at,
                    "id": event.id,
                }
            )

            notification_id = hashlib.sha256(encoded_data).hexdigest()
            notification_exists = Notification.objects.filter(
                notification_id=notification_id
            ).exists()

            stamp_name = event.data.get("provider", "<StampName>")
            if not notification_exists:
                Notification.objects.create(
                    notification_id=notification_id,
                    type="deduplication",
                    is_active=True,
                    title=f"'{stamp_name}' Duplicate Stamp Claim",
                    content=f"You have claimed the same '{stamp_name}' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet {address}. Learn more about deduplication <a href='https://github.com/orgs/gitcoinco/projects/6/views/link'>here</a>",
                    created_at=timezone.now().date(),
                    eth_address=address,
                )
