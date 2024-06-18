import pytest
import json
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from passport_admin.api import get_address
from passport_admin.models import Notification, DismissedNotification

pytestmark = pytest.mark.django_db

client = Client()
ETH_ADDRESS = "0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8"


class TestNotifications:
    def test_get_address(self):
        assert (
            get_address("did:pkh:eip155:1:0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8")
            == ETH_ADDRESS
        )

    def setUpTestData(cls):
        current_date = timezone.now().date()
        yesterday_date = current_date - timedelta(days=1)
        tomorrow_date = current_date + timedelta(days=1)

        # Generate custom non expired notifications
        cls.custom_active = Notification.objects.create(
            notification_id="custom_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active",
            content="Hello, this is a custom notification",
            created_at=yesterday_date,
            expires_at=tomorrow_date,
            eth_address=ETH_ADDRESS,
        )

        cls.custom_inactive = Notification.objects.create(
            notification_id="custom_inactive",
            type="custom",
            is_active=False,
            title="Custom Notification Inactive",
            content="Hello, this is a custom notification",
            created_at=yesterday_date,
            expires_at=tomorrow_date,
            eth_address=ETH_ADDRESS,
        )

        # Generate generic non expired notifications
        cls.generic_active = Notification.objects.create(
            notification_id="generic_active",
            type="generic",
            is_active=True,
            title="Generic Notification Active",
            content="Hello, this is a Generic notification",
            created_at=yesterday_date,
            expires_at=tomorrow_date,
        )

        cls.generic_inactive = Notification.objects.create(
            notification_id="generic_inactive",
            type="generic",
            is_active=False,
            title="Generic Notification Inactive",
            content="Hello, this is a Generic notification",
            created_at=yesterday_date,
            expires_at=tomorrow_date,
        )

        # Generate custom & generic expired active notifications
        cls.expired_custom_active = Notification.objects.create(
            notification_id="expired_custom_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active",
            content="Hello, this is a custom notification",
            created_at=yesterday_date - timedelta(days=2),
            expires_at=yesterday_date,
            eth_address=ETH_ADDRESS,
        )

        cls.expired_generic_active = Notification.objects.create(
            notification_id="expired_generic_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active",
            content="Hello, this is a custom notification",
            created_at=yesterday_date - timedelta(days=2),
            expires_at=yesterday_date,
            eth_address=ETH_ADDRESS,
        )

        # Generate active dismissed notifications
        cls.custom_dismissed_active = Notification.objects.create(
            notification_id="custom_dismissed_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active (Dismissed)",
            content="Hello, this is a custom notification",
            created_at=yesterday_date,
            expires_at=tomorrow_date,
            eth_address=ETH_ADDRESS,
        )

        cls.custom_dismissed = DismissedNotification.objects.create(
            notification=cls.dismissed_active, dismissed=True, eth_address=ETH_ADDRESS
        )

        cls.generic_dismissed_active = Notification.objects.create(
            notification_id="generic_dismissed_active",
            type="custom",
            is_active=True,
            title="Generic Notification Active (Dismissed)",
            content="Hello, this is a custom notification",
            created_at=yesterday_date,
            expires_at=tomorrow_date,
        )

        cls.generic_dismissed = DismissedNotification.objects.create(
            notification=cls.dismissed_active, dismissed=True, eth_address=ETH_ADDRESS
        )

    def test_get_active_notifications_for_address(self, sample_token):
        response = client.post(
            "/passport-admin/notification",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        assert response.json() == json.dump(
            {
                "items": [
                    {
                        "notification_id": self.custom_active.notification_id,
                        "type": self.custom_active.type,
                        "title": self.custom_active.title,
                        "content": self.custom_active.content,
                    },
                    {
                        "notification_id": self.generic_active.notification_id,
                        "type": self.generic_active.type,
                        "title": self.generic_active.title,
                        "content": self.generic_active.content,
                    },
                ]
            }
        )

    def test_dismiss_notification(self, sample_token):
        response = client.post(
            f"/passport-admin/notification/{self.custom_active.notification_id}/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        dismissed_notification = DismissedNotification.objects.get(
            notification=self.custom_active
        )
        assert dismissed_notification.dismissed is True
        assert dismissed_notification.eth_address == ETH_ADDRESS

    def test_dismiss_notification_invalid_id(self, sample_token):
        response = client.post(
            f"/passport-admin/notification/invalid_id/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "failed"}
