from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from ceramic_cache.models import Ban
from internal.schema import Credential, CredentialSubject


@pytest.fixture
def auth_headers():
    """Create authorization headers"""
    return {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}


@pytest.fixture
def sample_credentials():
    """Create sample credentials for testing"""
    return [
        Credential(
            credential_id="1",
            credentialSubject=CredentialSubject(
                hash="hash1",
                provider="github",
                address="0x1234567890123456789012345678901234567890",
            ),
        ),
        Credential(
            credential_id="2",
            credentialSubject=CredentialSubject(
                hash="hash2",
                provider="twitter",
                address="0x1234567890123456789012345678901234567890",
            ),
        ),
    ]


@pytest.mark.django_db
class TestCheckBansEndpoint:
    def test_check_bans_no_bans(self, client, auth_headers, sample_credentials):
        """Test when no bans exist"""
        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(not result["is_banned"] for result in data)
        assert all(result["ban_type"] is None for result in data)

    def test_check_bans_hash_ban(self, client, auth_headers, sample_credentials):
        """Test when a credential hash is banned"""
        Ban.objects.create(hash="hash1")

        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["is_banned"]  # First credential should be banned
        assert data[0]["ban_type"] == "hash"
        assert not data[1]["is_banned"]  # Second credential should not be banned

    def test_check_bans_address_ban(self, client, auth_headers, sample_credentials):
        """Test when an address is banned"""
        Ban.objects.create(address="0x1234567890123456789012345678901234567890")

        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(result["is_banned"] for result in data)
        assert all(result["ban_type"] == "account" for result in data)

    def test_check_bans_provider_specific(
        self, client, auth_headers, sample_credentials
    ):
        """Test when a specific provider is banned for an address"""
        Ban.objects.create(
            address="0x1234567890123456789012345678901234567890", provider="github"
        )

        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["is_banned"]  # Github credential should be banned
        assert data[0]["ban_type"] == "single_stamp"
        assert not data[1]["is_banned"]  # Twitter credential should not be banned

    def test_check_bans_temporary_ban(self, client, auth_headers, sample_credentials):
        """Test temporary ban with end_time"""
        future_date = timezone.now() + timedelta(days=1)
        Ban.objects.create(hash="hash1", end_time=future_date, reason="Temporary ban")

        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
            **auth_headers,
        )

        print(response.json())

        assert response.status_code == 200
        data = response.json()
        assert data[0]["is_banned"]
        assert data[0]["end_time"] is not None
        assert data[0]["reason"] == "Temporary ban"

    def test_check_bans_expired_ban(self, client, auth_headers, sample_credentials):
        """Test expired ban should not affect credentials"""
        past_date = timezone.now() - timedelta(days=1)
        Ban.objects.create(hash="hash1", end_time=past_date)

        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert not any(result["is_banned"] for result in data)

    def test_check_bans_multiple_addresses(self, client, auth_headers):
        """Test error when credentials have different addresses"""
        credentials = [
            Credential(
                credential_id="1",
                credentialSubject=CredentialSubject(
                    hash="hash1",
                    provider="github",
                    address="0x1111111111111111111111111111111111111111",
                ),
            ),
            Credential(
                credential_id="2",
                credentialSubject=CredentialSubject(
                    hash="hash2",
                    provider="twitter",
                    address="0x2222222222222222222222222222222222222222",
                ),
            ),
        ]

        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in credentials],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 400
        assert (
            "All credentials must be issued to the same address"
            in response.json()["detail"]
        )

    def test_check_bans_no_credentials(self, client, auth_headers):
        """Test error when no credentials provided"""
        response = client.post(
            "/internal/check-bans",
            data=[],
            content_type="application/json",
            **auth_headers,
        )

        assert response.status_code == 400
        assert "Must provide valid credential(s)" in response.json()["detail"]

    def test_check_bans_unauthorized(self, client, sample_credentials):
        """Test unauthorized access"""
        response = client.post(
            "/internal/check-bans",
            data=[c.dict() for c in sample_credentials],
            content_type="application/json",
        )

        assert response.status_code == 401
