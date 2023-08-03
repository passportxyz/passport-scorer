import pytest
from django.test import Client
from passport_admin.api import get_address
from passport_admin.models import DismissedBanners, PassportBanner

pytestmark = pytest.mark.django_db

client = Client()


class TestPassPortAdmin:
    def test_get_address(self):
        assert (
            get_address("did:pkh:eip155:1:0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8")
            == "0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8"
        )

    def test_get_banners(self, sample_token):
        response = client.get(
            "/passport-admin/banners",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        assert response.json() == []

    def test_dismiss_banner(self, sample_token, sample_address):
        banner = PassportBanner.objects.create(name="test", content="test", link="test")
        response = client.post(
            f"/passport-admin/banners/{banner.pk}/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )
        assert response.json() == {"status": "success"}
        dismissed_banner = DismissedBanners.objects.get(
            banner=banner, address=sample_address.lower()
        )
        assert dismissed_banner.banner == banner

    def test_dismiss_banner_does_not_exist(self, sample_token):
        response = client.post(
            "/passport-admin/banners/1/dismiss",
            {},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )  # Needs JWT Auth
        assert response.json() == {"status": "failed"}
