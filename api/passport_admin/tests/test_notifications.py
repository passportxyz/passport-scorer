import pytest
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from ceramic_cache.api.v1 import DbCacheToken
from passport_admin.models import Notification, NotificationStatus

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
def custom_notifications(current_date, sample_address):
    ret = {
        "active": Notification.objects.create(
            notification_id="custom_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "inactive": Notification.objects.create(
            notification_id="custom_inactive",
            type="custom",
            is_active=False,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "expired": Notification.objects.create(
            notification_id="expired_custom_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
        ),
        "read": Notification.objects.create(
            notification_id="custom_read_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "deleted": Notification.objects.create(
            notification_id="custom_deleted_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
    }

    NotificationStatus.objects.create(
        notification=ret["read"],
        is_read=True,
        eth_address=sample_address,
    )

    NotificationStatus.objects.create(
        notification=ret["deleted"],
        is_deleted=True,
        eth_address=sample_address,
    )

    return ret


@pytest.fixture
def generic_notifications(current_date, sample_address):
    ret = {
        "active": Notification.objects.create(
            notification_id="generic_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "inactive": Notification.objects.create(
            notification_id="generic_inactive",
            type="custom",
            is_active=False,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "expired": Notification.objects.create(
            notification_id="expired_generic_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
        ),
        "read": Notification.objects.create(
            notification_id="generic_read_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "deleted": Notification.objects.create(
            notification_id="generic_deleted_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
        ),
    }

    read = NotificationStatus.objects.create(
        notification=ret["read"],
        is_read=True,
        eth_address=sample_address,
    )
    print("read is read", read.is_read)

    NotificationStatus.objects.create(
        notification=ret["deleted"],
        is_deleted=True,
        eth_address=sample_address,
    )

    return ret


class TestNotifications:
    # def test_get_address(self, sample_address, sample_token):
    #     assert get_address(sample_token) == sample_address

    def test_get_active_notifications_for_address(
        self, sample_token, custom_notifications, generic_notifications
    ):
        response = client.post(
            "/passport-admin/notifications",
            {},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        expected_response = {
            "items": [
                {
                    "notification_id": custom_notifications["active"].notification_id,
                    "type": custom_notifications["active"].type,
                    "link": None,
                    "link_text": None,
                    "content": custom_notifications["active"].content,
                    "is_read": False,
                },
                {
                    "notification_id": custom_notifications["read"].notification_id,
                    "type": custom_notifications["read"].type,
                    "link": None,
                    "link_text": None,
                    "content": custom_notifications["read"].content,
                    "is_read": True,
                },
                {
                    "notification_id": generic_notifications["active"].notification_id,
                    "type": generic_notifications["active"].type,
                    "link": None,
                    "link_text": None,
                    "content": generic_notifications["active"].content,
                    "is_read": False,
                },
                {
                    "notification_id": generic_notifications["read"].notification_id,
                    "type": generic_notifications["read"].type,
                    "link": None,
                    "link_text": None,
                    "content": generic_notifications["read"].content,
                    "is_read": True,
                },
            ]
        }

        assert response.json() == expected_response

    def test_read_notification(
        self, sample_token, sample_address, custom_notifications
    ):
        notification_id = custom_notifications["active"].notification_id
        response = client.post(
            f"/passport-admin/notifications/{notification_id}",
            {
                "dismissal_type": "read",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        read_notification = NotificationStatus.objects.get(
            notification=custom_notifications["active"],
            is_read=True,
            eth_address=sample_address,
        )
        assert read_notification.is_read is True
        assert read_notification.eth_address == sample_address

    def test_delete_notification(
        self, sample_token, sample_address, custom_notifications
    ):
        notification_id = custom_notifications["active"].notification_id
        response = client.post(
            f"/passport-admin/notifications/{notification_id}",
            {
                "dismissal_type": "delete",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        deleted_notification = NotificationStatus.objects.get(
            notification=custom_notifications["active"],
            is_deleted=True,
            eth_address=sample_address,
        )
        assert deleted_notification.is_deleted is True
        assert deleted_notification.is_read is False
        assert deleted_notification.eth_address == sample_address

    def test_dismiss_notification_invalid_id(self, sample_token):
        response = client.post(
            "/passport-admin/notifications/invalid_id",
            {
                "dismissal_type": "read",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "failed"}
