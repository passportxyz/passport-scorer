import pytest
from django.conf import settings

from ceramic_cache.models import CeramicCache, Revocation


@pytest.fixture
def sample_stamp():
    """Create a sample stamp for testing"""
    return CeramicCache.objects.create(
        type=CeramicCache.StampType.V1,
        address="0x1234567890123456789012345678901234567890",
        provider="github",
        stamp={"proof": {"proofValue": "proof1"}},
        proof_value="proof1",
    )


@pytest.fixture
def revocation_url():
    return "/internal/check-revocations"


@pytest.mark.django_db
class TestCheckRevocationsEndpoint:
    def test_check_no_revocations(self, client, revocation_url):
        """Test when no revocations exist"""
        response = client.post(
            revocation_url,
            data={"proof_values": ["proof1", "proof2"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(not result["is_revoked"] for result in data)
        assert [r["proof_value"] for r in data] == ["proof1", "proof2"]

    def test_check_with_revocations(self, client, revocation_url, sample_stamp):
        """Test when some proof values are revoked"""
        # Create a revocation
        Revocation.objects.create(proof_value="proof1", ceramic_cache=sample_stamp)

        response = client.post(
            revocation_url,
            data={"proof_values": ["proof1", "proof2"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Check that proof1 is revoked but proof2 isn't
        revoked_statuses = {r["proof_value"]: r["is_revoked"] for r in data}
        assert revoked_statuses["proof1"] is True
        assert revoked_statuses["proof2"] is False

    def test_empty_proof_values(self, client, revocation_url):
        """Test with empty proof values list"""
        response = client.post(
            revocation_url,
            data={"proof_values": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_too_many_proof_values(self, client, revocation_url):
        """Test exceeding MAX_BULK_CACHE_SIZE limit"""
        too_many_proofs = [
            "proof" + str(i) for i in range(settings.MAX_BULK_CACHE_SIZE + 1)
        ]

        response = client.post(
            revocation_url,
            data={"proof_values": too_many_proofs},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 422
        assert "too many stamps" in str(response.content)

    def test_duplicate_proof_values(self, client, revocation_url, sample_stamp):
        """Test with duplicate proof values in request"""
        # Create a revocation
        Revocation.objects.create(proof_value="proof1", ceramic_cache=sample_stamp)

        response = client.post(
            revocation_url,
            data={"proof_values": ["proof1", "proof1"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(r["is_revoked"] for r in data)
        assert all(r["proof_value"] == "proof1" for r in data)

    def test_invalid_request_format(self, client, revocation_url):
        """Test with invalid request format"""
        response = client.post(
            revocation_url,
            data={"wrong_field": ["proof1"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 422  # Validation error

    def test_multiple_revocations(self, client, revocation_url):
        """Test checking multiple revocations"""
        # Create multiple stamps and revocations
        stamps = []
        for i in range(3):
            stamp = CeramicCache.objects.create(
                type=CeramicCache.StampType.V1,
                address=f"0x123456789012345678901234567890123456789{i}",
                provider="github",
                stamp={"proof": {"proofValue": f"proof{i}"}},
                proof_value=f"proof{i}",
            )
            stamps.append(stamp)

        # Revoke first and third stamps
        Revocation.objects.create(proof_value="proof0", ceramic_cache=stamps[0])
        Revocation.objects.create(proof_value="proof2", ceramic_cache=stamps[2])

        response = client.post(
            revocation_url,
            data={"proof_values": ["proof0", "proof1", "proof2"]},
            content_type="application/json",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        revoked_statuses = {r["proof_value"]: r["is_revoked"] for r in data}
        assert revoked_statuses["proof0"] is True
        assert revoked_statuses["proof1"] is False
        assert revoked_statuses["proof2"] is True
