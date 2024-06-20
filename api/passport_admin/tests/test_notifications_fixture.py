import pytest
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from passport_admin.api import get_address
from ceramic_cache.api.v1 import DbCacheToken
from passport_admin.models import Notification, NotificationStatus
from passport_admin.models import DismissedNotification

pytestmark = pytest.mark.django_db

client = Client()


@pytest.fixture
def sample_address():
    return "0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8"


@pytest.fixture
def sample_token(sample_address):
    token = DbCacheToken()
    token["token_type"] = "access"
    token["did"] = f"did:pkh:eip155:1:{sample_address.lower()}"

    return str(token)


@pytest.fixture
def current_date():
    return timezone.now().date()


@pytest.fixture
def custom_notification(current_date):
    ret = {
        "active": Notification.objects.create(
            notification_id="custom_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active",
            content="Hello, this is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "inactive": Notification.objects.create(
            notification_id="custom_inactive",
            type="custom",
            is_active=False,
            title="Custom Notification Inactive",
            content="Hello, this is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "expired": Notification.objects.create(
            notification_id="expired_custom_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active",
            content="Hello, this is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
        ),
        "dismissed": Notification.objects.create(
            notification_id="custom_dismissed_active",
            type="custom",
            is_active=True,
            title="Custom Notification Active (Dismissed)",
            content="Hello, this is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
        ),
    }

    NotificationStatus.objects.create(
        notification=ret["dismissed"],
        # dismissed=True,
        eth_address=sample_address,
    )

    return ret


@pytest.fixture
def generic_notification():
    ret = {
        "active": Notification.objects.create(
            notification_id="genereic_active",
            type="custom",
            is_active=True,
            title="Genereic Notification Active",
            content="Hello, this is a genereic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "inactive": Notification.objects.create(
            notification_id="genereic_inactive",
            type="custom",
            is_active=False,
            title="Genereic Notification Inactive",
            content="Hello, this is a genereic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "expired": Notification.objects.create(
            notification_id="expired_genereic_active",
            type="custom",
            is_active=True,
            title="Genereic Notification Active",
            content="Hello, this is a genereic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
        ),
        "dismissed": Notification.objects.create(
            notification_id="genereic_dismissed_active",
            type="custom",
            is_active=True,
            title="Genereic Notification Active (Dismissed)",
            content="Hello, this is a genereic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
        ),
    }

    DismissedNotification.objects.create(
        notification=ret["dismissed"],
        dismissed=True,
        eth_address=sample_address,
    )

    return ret


class TestNotifications:
    def test_get_address(self, sample_token):
        assert (
            get_address("did:pkh:eip155:1:0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8")
            == sample_address
        )

    def test_get_active_notifications_for_address(self, sample_token):
        response = client.post(
            "/passport-admin/notifications",
            {},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        # custom_notifications = {
        #     "active": Notification.objects.create(
        #         notification_id="custom_active",
        #         type="custom",
        #         is_active=True,
        #         title="Custom Notification Active",
        #         content="Hello, this is a custom notification",
        #         created_at=(current_date - timedelta(days=1)),
        #         expires_at=(current_date + timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        #     "inactive": Notification.objects.create(
        #         notification_id="custom_inactive",
        #         type="custom",
        #         is_active=False,
        #         title="Custom Notification Inactive",
        #         content="Hello, this is a custom notification",
        #         created_at=(current_date - timedelta(days=1)),
        #         expires_at=(current_date + timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        #     "expired": Notification.objects.create(
        #         notification_id="expired_custom_active",
        #         type="custom",
        #         is_active=True,
        #         title="Custom Notification Active",
        #         content="Hello, this is a custom notification",
        #         created_at=(current_date - timedelta(days=3)),
        #         expires_at=(current_date - timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        #     "dismissed": Notification.objects.create(
        #         notification_id="custom_dismissed_active",
        #         type="custom",
        #         is_active=True,
        #         title="Custom Notification Active (Dismissed)",
        #         content="Hello, this is a custom notification",
        #         created_at=(current_date - timedelta(days=3)),
        #         expires_at=(current_date - timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        # }

        # DismissedNotification.objects.create(
        #     notification=custom_notifications["dismissed"],
        #     dismissed=True,
        #     eth_address=sample_address,
        # )

        # generic_notifications = {
        #     "active": Notification.objects.create(
        #         notification_id="genereic_active",
        #         type="custom",
        #         is_active=True,
        #         title="Genereic Notification Active",
        #         content="Hello, this is a genereic notification",
        #         created_at=(current_date - timedelta(days=1)),
        #         expires_at=(current_date + timedelta(days=1)),
        #     ),
        #     "inactive": Notification.objects.create(
        #         notification_id="genereic_inactive",
        #         type="custom",
        #         is_active=False,
        #         title="Genereic Notification Inactive",
        #         content="Hello, this is a genereic notification",
        #         created_at=(current_date - timedelta(days=1)),
        #         expires_at=(current_date + timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        #     "expired": Notification.objects.create(
        #         notification_id="expired_genereic_active",
        #         type="custom",
        #         is_active=True,
        #         title="Genereic Notification Active",
        #         content="Hello, this is a genereic notification",
        #         created_at=(current_date - timedelta(days=3)),
        #         expires_at=(current_date - timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        #     "dismissed": Notification.objects.create(
        #         notification_id="genereic_dismissed_active",
        #         type="custom",
        #         is_active=True,
        #         title="Genereic Notification Active (Dismissed)",
        #         content="Hello, this is a genereic notification",
        #         created_at=(current_date - timedelta(days=3)),
        #         expires_at=(current_date - timedelta(days=1)),
        #         eth_address=sample_address,
        #     ),
        # }

        # DismissedNotification.objects.create(
        #     notification=generic_notifications["dismissed"],
        #     dismissed=True,
        #     eth_address=sample_address,
        # )

        # print(Notification.objects.all())
        assert response.json() == {
            "items": [
                {
                    "notification_id": custom_notification["active"].notification_id,
                    "type": custom_notification["active"].type,
                    "title": custom_notification["active"].title,
                    "content": custom_notification["active"].content,
                },
                # {
                #     "notification_id": self.generic_active.notification_id,
                #     "type": self.generic_active.type,
                #     "title": self.generic_active.title,
                #     "content": self.generic_active.content,
                # },
            ]
        }

        assert response.json() == {"items": [{}]}

    def test_dismiss_notification(self, sample_token, custom_notification):
        print("custom_active: ", custom_notification)
        response = client.post(
            f"/passport-admin/notifications/{custom_notification.notification_id}/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        dismissed_notification = NotificationStatus.objects.get(
            notification=self.custom_active
        )
        assert dismissed_notification.dismissed is True
        assert dismissed_notification.eth_address == sample_address

    def test_dismiss_notification_invalid_id(self, sample_token):
        response = client.post(
            "/passport-admin/notifications/invalid_id/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "failed"}
