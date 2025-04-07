# pylint: disable=redefined-outer-name
"""
This module contains unit tests for the notifications functionality in the passport_admin app.
"""

import hashlib
from datetime import timedelta

import dag_cbor
import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from account.models import Community
from ceramic_cache.api.v1 import DbCacheToken
from ceramic_cache.models import CeramicCache
from passport_admin.models import Notification, NotificationStatus
from registry.models import Event
from scorer_weighted.models import BinaryWeightedScorer, Scorer

pytestmark = pytest.mark.django_db

client = Client()


def get_hash(stamp):
    cs = stamp["credentialSubject"]
    if "hash" in cs:
        return cs["hash"]
    return cs["nullifiers"][0]


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
def sample_bad_token(sample_address):
    token = DbCacheToken()
    token["token_type"] = "access"
    token["did"] = f"did:pkh:eip155:bad-did"

    return str(token)


@pytest.fixture
def current_date():
    return timezone.now().date()


@pytest.fixture
def custom_notifications(current_date, sample_address, community):
    ret = {
        "active": Notification.objects.create(
            notification_id="custom_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
            community=community,
        ),
        "inactive": Notification.objects.create(
            notification_id="custom_inactive",
            type="custom",
            is_active=False,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
            community=community,
        ),
        "expired": Notification.objects.create(
            notification_id="expired_custom_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
            community=community,
        ),
        "read": Notification.objects.create(
            notification_id="custom_read_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
            community=community,
        ),
        "deleted": Notification.objects.create(
            notification_id="custom_deleted_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
            community=community,
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


scorer_weights = {"provider-1": "0.5", "provider-2": "0.5"}


@pytest.fixture
def community(scorer_account, weight_config):
    scorer = BinaryWeightedScorer.objects.create(
        type=Scorer.Type.WEIGHTED_BINARY, weights=scorer_weights
    )
    comm = Community.objects.create(
        name="Community 1",
        description="Community 1 - testing",
        account=scorer_account,
        scorer=scorer,
    )
    settings.CERAMIC_CACHE_SCORER_ID = comm.id
    return comm


@pytest.fixture
def generic_notifications(current_date, sample_address, community):
    ret = {
        "active": Notification.objects.create(
            notification_id="generic_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            community=community,
        ),
        "inactive": Notification.objects.create(
            notification_id="generic_inactive",
            type="custom",
            is_active=False,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            community=community,
        ),
        "expired": Notification.objects.create(
            notification_id="expired_generic_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            community=community,
        ),
        "read": Notification.objects.create(
            notification_id="generic_read_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            community=community,
        ),
        "deleted": Notification.objects.create(
            notification_id="generic_deleted_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            community=community,
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
def deduplication_event(sample_address, community):
    event = Event.objects.create(
        action=Event.Action.LIFO_DEDUPLICATION,
        address=sample_address,
        data={
            "hash": "some_hash",
            "provider": "provider-1",
            "community_id": "some_community_id",
        },
        community=community,
    )
    return event


@pytest.fixture(
    params=[
        {"credentialSubject": {"hash": "some_hash", "id": "some_id"}},
        {"credentialSubject": {"nullifiers": ["some_hash"], "id": "some_id"}},
    ]
)
def expired_stamp(sample_address, request):
    cc_expired = CeramicCache.objects.create(
        address=sample_address,
        provider="provider-1",
        created_at=timezone.now() - timedelta(days=30),
        stamp=request.param,
        expiration_date=timezone.now() - timedelta(days=3),
        issuance_date=timezone.now() - timedelta(days=3),
    )

    CeramicCache.objects.create(
        address=sample_address,
        provider="provider-2",
        deleted_at=timezone.now(),
        created_at=timezone.now() - timedelta(days=3),
        stamp=request.param,
        expiration_date=timezone.now() + timedelta(days=30),
        issuance_date=timezone.now() - timedelta(days=3),
    )

    return cc_expired


@pytest.fixture
def existing_notification_expired_chain(sample_address, community):
    return Notification.objects.create(
        notification_id=hashlib.sha256(
            dag_cbor.encode(
                {
                    "chain_id": "chain1",
                    "chain_name": "Chain 1",
                    "address": sample_address,
                }
            )
        ).hexdigest(),
        type="on_chain_expiry",
        link=None,
        link_text=None,
        content="Your onchain Passport on Chain 1 has expired. Update now to maintain your active status.",
        is_active=True,
        eth_address=sample_address,
        created_at=timezone.now() - timedelta(days=3),
        community=community,
    )


@pytest.fixture(
    params=[
        {"credentialSubject": {"hash": "some_hash", "id": "some_id"}},
        {"credentialSubject": {"nullifiers": ["some_hash"], "id": "some_id"}},
    ]
)
def existing_notification_expired_stamp(sample_address, community, request):
    cc_expired = CeramicCache.objects.create(
        address=sample_address,
        provider="provider-1",
        created_at=timezone.now() - timedelta(days=30),
        stamp=request.param,
        expiration_date=timezone.now() - timedelta(days=3),
        issuance_date=timezone.now() - timedelta(days=3),
    )

    return Notification.objects.create(
        notification_id=hashlib.sha256(
            dag_cbor.encode(
                {
                    "cc_id": cc_expired.id,
                    "cc_provider": cc_expired.provider,
                    "cc_stamp_hash": get_hash(cc_expired.stamp),
                    "cc_stamp_id": cc_expired.stamp["credentialSubject"]["id"],
                    "address": sample_address,
                }
            )
        ).hexdigest(),
        type="stamp_expiry",
        link="provider-1",
        link_text=None,
        content=f"Your {cc_expired.provider} stamp has expired. Please reverify to keep your Passport up to date.",
        is_active=True,
        created_at=timezone.now() - timedelta(days=3),
        eth_address=sample_address,
        community=community,
    )


@pytest.fixture
def existing_notification_deduplication_event(sample_address, community):
    event = Event.objects.create(
        action=Event.Action.LIFO_DEDUPLICATION,
        address=sample_address,
        data={
            "hash": "some_hash",
            "provider": "provider-1",
            "community_id": community.id,
        },
    )
    stamp_name = event.data.get("provider", "<StampName>")
    return Notification.objects.create(
        notification_id=hashlib.sha256(
            dag_cbor.encode(
                {
                    "action": event.action,
                    "address": event.address,
                    "data": event.data,
                    "id": event.id,
                }
            )
        ).hexdigest(),
        content=f"You have claimed the same '{stamp_name}' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet {event.address}. Learn more about deduplication",
        link="https://support.passport.xyz/passport-knowledge-base/using-passport/common-questions/why-is-my-passport-score-not-adding-up",
        link_text="here",
        type="deduplication",
        is_active=True,
        created_at=timezone.now() - timedelta(days=3),
        eth_address=sample_address,
        community=community,
    )


class TestNotifications:
    def test_get_active_notifications_for_address(
        self,
        sample_token,
        sample_address,
        custom_notifications,
        generic_notifications,
        deduplication_event,
        expired_stamp,
        current_date,
        community,
    ):
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        expected_deduplication_notification = {
            "notification_id": hashlib.sha256(
                dag_cbor.encode(
                    {
                        "action": deduplication_event.action,
                        "address": deduplication_event.address,
                        "data": deduplication_event.data,
                        "id": deduplication_event.id,
                    }
                )
            ).hexdigest(),
            "type": "deduplication",
            "link": "https://support.passport.xyz/passport-knowledge-base/using-passport/common-questions/why-is-my-passport-score-not-adding-up",
            "link_text": "here",
            "content": f"You have claimed the same '{deduplication_event.data['provider']}' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet {sample_address}. Learn more about deduplication",
            "created_at": current_date.isoformat(),
            "is_read": False,
        }

        expected_expired_stamp_notification = {
            "notification_id": hashlib.sha256(
                dag_cbor.encode(
                    {
                        "cc_id": expired_stamp.id,
                        "cc_provider": expired_stamp.provider,
                        "cc_stamp_hash": get_hash(expired_stamp.stamp),
                        "cc_stamp_id": expired_stamp.stamp["credentialSubject"]["id"],
                        "address": sample_address,
                    }
                )
            ).hexdigest(),
            "type": "stamp_expiry",
            "link": "provider-1",
            "link_text": None,
            "content": f"Your {expired_stamp.provider} stamp has expired. Please reverify to keep your Passport up to date.",
            "created_at": current_date.isoformat(),
            "is_read": False,
        }

        expected_response_items = sorted(
            [
                {
                    "notification_id": custom_notifications["active"].notification_id,
                    "type": custom_notifications["active"].type,
                    "link": None,
                    "link_text": None,
                    "content": custom_notifications["active"].content,
                    "created_at": custom_notifications["active"].created_at.isoformat(),
                    "is_read": False,
                },
                {
                    "notification_id": custom_notifications["read"].notification_id,
                    "type": custom_notifications["read"].type,
                    "link": None,
                    "link_text": None,
                    "content": custom_notifications["read"].content,
                    "created_at": custom_notifications["read"].created_at.isoformat(),
                    "is_read": True,
                },
                {
                    "notification_id": generic_notifications["active"].notification_id,
                    "type": generic_notifications["active"].type,
                    "link": None,
                    "link_text": None,
                    "content": generic_notifications["active"].content,
                    "created_at": generic_notifications[
                        "active"
                    ].created_at.isoformat(),
                    "is_read": False,
                },
                {
                    "notification_id": generic_notifications["read"].notification_id,
                    "type": generic_notifications["read"].type,
                    "link": None,
                    "link_text": None,
                    "content": generic_notifications["read"].content,
                    "created_at": generic_notifications["read"].created_at.isoformat(),
                    "is_read": True,
                },
                expected_deduplication_notification,
                expected_expired_stamp_notification,
            ],
            key=lambda x: x["notification_id"],
        )

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])

        assert received_items == expected_response_items

    def test_expired_chain(self, sample_token, sample_address, current_date, community):
        response = client.post(
            "/passport-admin/notifications",
            {
                "expired_chain_ids": [
                    {"id": "chain1", "name": "Chain 1"},
                    {"id": "chain2", "name": "Chain 2"},
                ],
                "scorer_id": community.id,
            },
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        expected_response = sorted(
            [
                {
                    "notification_id": hashlib.sha256(
                        dag_cbor.encode(
                            {
                                "chain_id": "chain1",
                                "chain_name": "Chain 1",
                                "address": sample_address,
                            }
                        )
                    ).hexdigest(),
                    "type": "on_chain_expiry",
                    "link": None,
                    "link_text": None,
                    "content": "Your onchain Passport on Chain 1 has expired. Update now to maintain your active status.",
                    "created_at": current_date.isoformat(),
                    "is_read": False,
                },
                {
                    "notification_id": hashlib.sha256(
                        dag_cbor.encode(
                            {
                                "chain_id": "chain2",
                                "chain_name": "Chain 2",
                                "address": sample_address,
                            }
                        )
                    ).hexdigest(),
                    "type": "on_chain_expiry",
                    "link": None,
                    "link_text": None,
                    "content": "Your onchain Passport on Chain 2 has expired. Update now to maintain your active status.",
                    "created_at": current_date.isoformat(),
                    "is_read": False,
                },
            ],
            key=lambda x: x["notification_id"],
        )

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])
        assert expected_response == received_items

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

    def test_no_duplication_notifications_expired_chain(
        self, sample_token, existing_notification_expired_chain, community
    ):
        existing = Notification.objects.filter(
            notification_id=existing_notification_expired_chain.notification_id
        ).all()

        assert existing.count() == 1

        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {
                "expired_chain_ids": [
                    {"id": "chain1", "name": "Chain 1"},
                ],
                "scorer_id": community.id,
            },
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        after_call_existing = Notification.objects.filter(
            notification_id=existing_notification_expired_chain.notification_id
        ).all()

        assert after_call_existing.count() == 1
        expected_response = [
            {
                "notification_id": existing_notification_expired_chain.notification_id,
                "type": existing_notification_expired_chain.type,
                "link": existing_notification_expired_chain.link,
                "link_text": existing_notification_expired_chain.link_text,
                "content": existing_notification_expired_chain.content,
                "created_at": existing_notification_expired_chain.created_at.isoformat(),
                "is_read": False,
            }
        ]

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])
        assert expected_response == received_items

    def test_no_duplication_notifications_expired_stamp(
        self,
        sample_token,
        existing_notification_expired_stamp,
        community,
    ):
        existing = Notification.objects.filter(
            notification_id=existing_notification_expired_stamp.notification_id
        ).all()
        assert existing.count() == 1

        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        after_call_existing = Notification.objects.filter(
            notification_id=existing_notification_expired_stamp.notification_id
        ).all()

        assert after_call_existing.count() == 1
        expected_response = [
            {
                "notification_id": existing_notification_expired_stamp.notification_id,
                "type": existing_notification_expired_stamp.type,
                "link": existing_notification_expired_stamp.link,
                "link_text": existing_notification_expired_stamp.link_text,
                "content": existing_notification_expired_stamp.content,
                "created_at": existing_notification_expired_stamp.created_at.isoformat(),
                "is_read": False,
            }
        ]

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])
        assert expected_response == received_items

    def test_only_valid_stamps_generate_expired_notifications(
        self,
        sample_token,
        existing_notification_expired_stamp,
        community,
        sample_address,
    ):
        cc_expired = CeramicCache.objects.create(
            address=sample_address,
            provider="old-provider",
            created_at=timezone.now() - timedelta(days=30),
            stamp={"credentialSubject": {"hash": "some_hash", "id": "some_id"}},
            expiration_date=timezone.now() - timedelta(days=3),
            issuance_date=timezone.now() - timedelta(days=3),
        )

        use_cache_count = CeramicCache.objects.filter(
            address=sample_address, deleted_at__isnull=True
        ).count()

        assert use_cache_count == 2
        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        expected_response = [
            {
                "notification_id": existing_notification_expired_stamp.notification_id,
                "type": existing_notification_expired_stamp.type,
                "link": existing_notification_expired_stamp.link,
                "link_text": existing_notification_expired_stamp.link_text,
                "content": existing_notification_expired_stamp.content,
                "created_at": existing_notification_expired_stamp.created_at.isoformat(),
                "is_read": False,
            }
        ]

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])
        assert expected_response == received_items

    def test_deduplication_events_are_returned_for_requested_scorer(
        self,
        sample_token,
        sample_address,
        existing_notification_deduplication_event,
        scorer_account,
        community,
    ):
        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY, weights=scorer_weights
        )
        other_community = Community.objects.create(
            name="Community 2",
            description="Community 2 - testing",
            account=scorer_account,
            scorer=scorer,
        )
        Event.objects.create(
            action=Event.Action.LIFO_DEDUPLICATION,
            address=sample_address,
            data={
                "hash": "some_hash",
                "provider": "provider-2",
                "community_id": other_community.id,
            },
            community=other_community,
        )
        current_event_count = Event.objects.filter(address=sample_address).count()
        assert current_event_count == 2

        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        res = response.json()
        assert len(res["items"]) == 1
        assert (
            res["items"][0]["content"]
            == "You have claimed the same 'provider-1' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet 0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8. Learn more about deduplication"
        )

    def test_notifications_are_returned_for_requested_scorer_for_providers_w_points(
        self,
        sample_token,
        sample_address,
        existing_notification_deduplication_event,
        community,
    ):
        Event.objects.create(
            action=Event.Action.LIFO_DEDUPLICATION,
            address=sample_address,
            data={
                "hash": "some_hash",
                "provider": "old-provider",
                "community_id": community.id,
            },
            community=community,
        )
        current_event_count = Event.objects.filter(address=sample_address).count()
        assert current_event_count == 2

        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        res = response.json()
        assert len(res["items"]) == 1
        assert (
            res["items"][0]["content"]
            == "You have claimed the same 'provider-1' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet 0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8. Learn more about deduplication"
        )

    def test_no_duplication_notifications_deduplication_event(
        self, sample_token, existing_notification_deduplication_event, community
    ):
        existing = Notification.objects.filter(
            notification_id=existing_notification_deduplication_event.notification_id
        ).all()
        assert existing.count() == 1

        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        after_call_existing = Notification.objects.filter(
            notification_id=existing_notification_deduplication_event.notification_id
        ).all()

        assert after_call_existing.count() == 1
        expected_response = [
            {
                "notification_id": existing_notification_deduplication_event.notification_id,
                "type": existing_notification_deduplication_event.type,
                "link": existing_notification_deduplication_event.link,
                "link_text": existing_notification_deduplication_event.link_text,
                "content": existing_notification_deduplication_event.content,
                "created_at": existing_notification_deduplication_event.created_at.isoformat(),
                "is_read": False,
            }
        ]

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])
        assert expected_response == received_items

    def test_delete_all_notifications_success(
        self, sample_token, sample_address, custom_notifications, community
    ):
        """Test successful deletion of all active notifications for a user"""
        response = client.delete(
            "/passport-admin/notifications",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        notification_statuses = NotificationStatus.objects.filter(
            eth_address=sample_address,
            is_deleted=True,
        )

        notification_statuses = NotificationStatus.objects.filter(
            eth_address=sample_address
        )

        assert notification_statuses.count() == 4

    def test_delete_all_notifications_error(self, sample_bad_token):
        """Test error handling in delete all notifications endpoint"""

        response = client.delete(
            "/passport-admin/notifications",
            HTTP_AUTHORIZATION=f"Bearer {sample_bad_token}",
        )

        assert response.json() == {"status": "failed"}

    def test_no_old_deduplication_events(self, sample_token, sample_address, community):
        """
        Test that no deduplication notifications are generated for events older than 30 days
        """
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Generate deduplication events older than 30 days
        for i in range(5):
            obj = Event.objects.create(
                action=Event.Action.LIFO_DEDUPLICATION,
                address=sample_address,
                data={
                    "hash": "some_hash",
                    "provider": "provider-1",
                    "community_id": "some_community_id",
                },
            )
            obj.created_at = thirty_days_ago - timedelta(days=i)
            obj.save()

        deduplication_events = Event.objects.filter(
            action=Event.Action.LIFO_DEDUPLICATION,
            address=sample_address,
        )
        assert deduplication_events.count() == 5

        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        res = response.json()
        received_items = sorted(res["items"], key=lambda x: x["notification_id"])
        assert len(received_items) == 0

    def test_max_20_active_notifications(self, sample_token, sample_address, community):
        """
        Test that only the 20 newest notifications are returned
        """
        for i in range(25):
            notification = Notification.objects.create(
                notification_id=f"notification_{i}",
                type="custom",
                is_active=True,
                content=f"Hello! This is a custom notification {i}",
                eth_address=sample_address,
                community=community,
            )
            notification.created_at = timezone.now() - timedelta(days=i)
            notification.save()

        notifications = Notification.objects.filter(eth_address=sample_address)
        assert notifications.count() == 25

        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        res = response.json()
        assert len(res["items"]) == 20

        newest_created_at = max(res["items"], key=lambda x: x["created_at"])[
            "created_at"
        ]
        oldest_created_at = min(res["items"], key=lambda x: x["created_at"])[
            "created_at"
        ]
        assert (
            res["items"][0]["notification_id"] == "notification_0"
        )  # Newest notification
        assert res["items"][0]["created_at"] == newest_created_at
        assert (
            res["items"][-1]["notification_id"] == "notification_19"
        )  # Oldest notification

        assert res["items"][-1]["created_at"] == oldest_created_at

    def test_deduplication_events_are_returned_for_signed_in_user(
        self, sample_token, sample_address, community
    ):
        """
        This tests that only a users notifications are returned
        """
        notification = Notification.objects.create(
            notification_id=f"notification_1",
            type="custom",
            is_active=True,
            content=f"Hello! This is a custom notification 1",
            eth_address=sample_address,
            community=community,
        )
        notification.created_at = timezone.now() - timedelta(days=1)
        notification.save()

        notification = Notification.objects.create(
            notification_id=f"notification_2",
            type="custom",
            is_active=True,
            content=f"Hello! This is a custom notification 2",
            eth_address="sample_address",
            community=community,
        )
        notification.created_at = timezone.now() - timedelta(days=2)
        notification.save()

        assert Notification.objects.all().count() == 2

        notifications = Notification.objects.filter(eth_address=sample_address)
        assert notifications.count() == 1

        # Call the same endpoint again to check if the same notifications are returned
        response = client.post(
            "/passport-admin/notifications",
            {"scorer_id": community.id},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        res = response.json()
        assert len(res["items"]) == 1
