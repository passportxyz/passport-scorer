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

    def test_get_banners_default(self, sample_token):
        banner = PassportBanner.objects.create(content="test", link="test")
        response = client.get(
            "/passport-admin/banners",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        assert response.json() == [
            {
                "application": "passport",
                "banner_id": banner.id,
                "content": "test",
                "link": "test",
                "display_on_all_dashboards": True,
            }
        ]

    def test_get_banners_filtered(self, sample_token):
        banner_passport = PassportBanner.objects.create(content="test", link="test")
        banner_staking = PassportBanner.objects.create(
            content="test_staking", link="test_staking_link", application="staking"
        )
        # Test getting passport banners
        response = client.get(
            "/passport-admin/banners?application=passport",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        assert response.json() == [
            {
                "application": "passport",
                "banner_id": banner_passport.id,
                "content": "test",
                "link": "test",
                "display_on_all_dashboards": True,
            }
        ]
        # Test getting staking banners
        response = client.get(
            "/passport-admin/banners?application=staking",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )
        assert response.json() == [
            {
                "application": "staking",
                "banner_id": banner_staking.id,
                "content": "test_staking",
                "link": "test_staking_link",
                "display_on_all_dashboards": True,
            }
        ]

    def test_dismiss_banner(self, sample_token, sample_address):
        banner = PassportBanner.objects.create(content="test", link="test")
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
