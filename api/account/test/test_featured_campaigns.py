import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from account.models import Account, Community, Customization, FeaturedCampaign
from scorer.test.conftest import weight_config  # noqa: F401

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def customization(weight_config):  # noqa: F811
    user = User.objects.create_user(username="campaign-test-user", password="12345")
    account = Account.objects.create(user=user, address="0xCAMPAIGNTEST")
    community = Community.objects.create(
        name="campaign-community", description="Test", account=account
    )
    return Customization.objects.create(path="campaign-test", scorer=community)


@pytest.fixture
def campaigns(db):
    # Two campaigns share an image, so image_tag cannot identify them.
    common = {
        "partner_name": "Partner",
        "image_tag": "shared-image",
        "header_text": "Header",
        "body_text": "Body",
        "destination_url": "https://example.com",
    }
    first = FeaturedCampaign.objects.create(
        **common, audience_label="For builders", details_text="Line one\nLine two"
    )
    second = FeaturedCampaign.objects.create(**common, display_order=1)
    return first, second


def assert_campaigns(response, campaigns):
    assert response.status_code == 200
    returned = response.json()["featuredCampaigns"]
    first, second = campaigns

    assert [c["id"] for c in returned] == [str(first.pk), str(second.pk)]
    assert all(c["imageTag"] == "shared-image" for c in returned)
    assert returned[0]["audienceLabel"] == "For builders"
    assert returned[0]["details"] == "Line one\nLine two"
    assert returned[1]["audienceLabel"] == ""
    assert returned[1]["details"] == ""


def test_base_customization_campaign_ids_are_unique(campaigns):
    assert_campaigns(Client().get("/account/customization"), campaigns)


def test_dashboard_customization_campaign_ids_are_unique(customization, campaigns):
    response = Client().get(f"/account/customization/{customization.path}/")
    assert_campaigns(response, campaigns)
