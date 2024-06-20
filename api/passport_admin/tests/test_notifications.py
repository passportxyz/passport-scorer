import pytest
import json
from django.test import Client, TestCase
from django.utils import timezone
from datetime import timedelta

from passport_admin.api import get_address
from ceramic_cache.api.v1 import DbCacheToken
from passport_admin.models import Notification, NotificationStatus

pytestmark = pytest.mark.django_db

client = Client()


class TestNotifications(TestCase):
    def setUp(self):
        self.sample_address = "0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8"
        self.sample_token = (
            "did:pkh:eip155:1:0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8"
        )

        # self.sample_token = DbCacheToken()
        # self.sample_token["token_type"] = "access"
        # self.sample_token["did"] = f"did:pkh:eip155:1:{self.sample_address.lower()}"
        self.current_date = timezone.now().date()
        self.custom_notifications = {
            "active": Notification.objects.create(
                notification_id="custom_active",
                type="custom",
                is_active=True,
                title="Custom Notification Active",
                content="Hello, this is a custom notification",
                created_at=(self.current_date - timedelta(days=1)),
                expires_at=(self.current_date + timedelta(days=1)),
                eth_address=self.sample_address,
            ),
            "inactive": Notification.objects.create(
                notification_id="custom_inactive",
                type="custom",
                is_active=False,
                title="Custom Notification Inactive",
                content="Hello, this is a custom notification",
                created_at=(self.current_date - timedelta(days=1)),
                expires_at=(self.current_date + timedelta(days=1)),
                eth_address=self.sample_address,
            ),
            "expired": Notification.objects.create(
                notification_id="expired_custom_active",
                type="custom",
                is_active=True,
                title="Custom Notification Active",
                content="Hello, this is a custom notification",
                created_at=(self.current_date - timedelta(days=3)),
                expires_at=(self.current_date - timedelta(days=1)),
                eth_address=self.sample_address,
            ),
            "dismissed": Notification.objects.create(
                notification_id="custom_dismissed_active",
                type="custom",
                is_active=True,
                title="Custom Notification Active (Dismissed)",
                content="Hello, this is a custom notification",
                created_at=(self.current_date - timedelta(days=3)),
                expires_at=(self.current_date - timedelta(days=1)),
                eth_address=self.sample_address,
            ),
        }

        NotificationStatus.objects.create(
            notification=self.custom_notifications["dismissed"],
            # dismissed=True,
            eth_address=self.sample_address,
        )

        self.generic_notifications = {
            "active": Notification.objects.create(
                notification_id="genereic_active",
                type="custom",
                is_active=True,
                title="Genereic Notification Active",
                content="Hello, this is a genereic notification",
                created_at=(self.current_date - timedelta(days=1)),
                expires_at=(self.current_date + timedelta(days=1)),
            ),
            "inactive": Notification.objects.create(
                notification_id="genereic_inactive",
                type="custom",
                is_active=False,
                title="Genereic Notification Inactive",
                content="Hello, this is a genereic notification",
                created_at=(self.current_date - timedelta(days=1)),
                expires_at=(self.current_date + timedelta(days=1)),
            ),
            "expired": Notification.objects.create(
                notification_id="expired_genereic_active",
                type="custom",
                is_active=True,
                title="Genereic Notification Active",
                content="Hello, this is a genereic notification",
                created_at=(self.current_date - timedelta(days=3)),
                expires_at=(self.current_date - timedelta(days=1)),
            ),
            "dismissed": Notification.objects.create(
                notification_id="genereic_dismissed_active",
                type="custom",
                is_active=True,
                title="Genereic Notification Active (Dismissed)",
                content="Hello, this is a genereic notification",
                created_at=(self.current_date - timedelta(days=3)),
                expires_at=(self.current_date - timedelta(days=1)),
            ),
        }

        NotificationStatus.objects.create(
            notification=self.generic_notifications["dismissed"],
            # dismissed=True,
            eth_address=self.sample_address,
        )

    # TODO: this ain't working

    # def test_get_address(self):
    #     assert get_address(self.sample_token) == self.sample_address

    def test_get_active_notifications_for_address(self):
        response = client.post(
            "/passport-admin/notifications",
            {},
            HTTP_AUTHORIZATION=f"Bearer {self.sample_token}",
            content_type="application/json",
        )
        expected_response = {
            "items": [
                {
                    "notification_id": self.custom_notifications[
                        "active"
                    ].notification_id,
                    "type": self.custom_notifications["active"].type,
                    "title": self.custom_notifications["active"].title,
                    "content": self.custom_notifications["active"].content,
                },
                {
                    "notification_id": self.generic_notifications[
                        "active"
                    ].notification_id,
                    "type": self.generic_notifications["active"].type,
                    "title": self.generic_notifications["active"].title,
                    "content": self.generic_notifications["active"].content,
                },
            ]
        }

        assert response.json() == expected_response

    def test_dismiss_notification(self):
        notification_id = self.custom_notifications["active"].notification_id
        response = client.post(
            f"/passport-admin/notifications/{notification_id}/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.sample_token}",
        )

        assert response.json() == {"status": "success"}

        dismissed_notification = NotificationStatus.objects.get(
            notification=self.custom_notifications["active"],
            # dismissed=True,
            eth_address=self.sample_address,
        )
        assert dismissed_notification.dismissed is True
        assert dismissed_notification.eth_address == self.sample_address

    def test_dismiss_notification_invalid_id(self):
        response = client.post(
            "/passport-admin/notifications/invalid_id/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.sample_token}",
        )

        assert response.json() == {"status": "failed"}

    # TODO: @Larisa complete tests for expired stamp & deduplication notifications
