from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.conf import settings

from ceramic_cache.api.schema import (
    CachedStampResponse,
    CacheStampPayload,
    GetStampsWithScoreResponse,
)
from registry.exceptions import InvalidAddressException
from v2.schema import V2ScoreResponse


@pytest.fixture
def valid_address():
    return "0x394EFd95c167fF30EE8668C24B281487f43D2122"


@pytest.fixture
def sample_credential(valid_address):
    now = datetime.utcnow()
    return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": "did:pkh:eip155:1:" + valid_address,
            "provider": "github",
            "@context": [{"@version": 1.1}],
            "hash": "abc123",
            "address": valid_address,
        },
        "issuer": "did:key:issuer123",
        "issuanceDate": now.isoformat(),
        "expirationDate": (now + timedelta(days=30)).isoformat(),
        "proof": {
            "@context": "https://w3id.org/security/suites/eip712-2022/v1",
            "type": "EthereumEip712Signature2022",
            "proofPurpose": "assertionMethod",
            "proofValue": "0xproof123",
            "verificationMethod": "did:key:method123",
            "created": now.isoformat(),
            "eip712Domain": {
                "domain": {"name": "TestDomain"},
                "primaryType": "VerifiableCredential",
                "types": {"EIP712Domain": [{"name": "name", "type": "string"}]},
            },
        },
    }


@pytest.fixture
def valid_payload(sample_credential):
    return {"scorer_id": 1, "stamps": [sample_credential]}


@pytest.fixture
def mock_success_response(valid_address, sample_credential):
    return GetStampsWithScoreResponse(
        success=True,
        stamps=[
            CachedStampResponse(
                address=valid_address, provider="github", stamp=sample_credential, id=1
            )
        ],
        score=V2ScoreResponse(
            score=0.5,
            stats={
                "rawScore": 0.5,
                "threshold": 0.5,
                "provider_stats": {"github": {"stamp_weight": 0.3, "confidence": 0.8}},
            },
            status="DONE",
        ),
    )


@pytest.mark.django_db
class TestAddStampsEndpoint:
    def test_missing_auth_header(self, client, valid_address, valid_payload):
        """Test that requests without auth header fail"""
        response = client.post(f"/internal/stamps/{valid_address}", json=valid_payload)
        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]

    def test_invalid_auth_header(self, client, valid_address, valid_payload):
        """Test that requests with invalid auth token fail"""
        response = client.post(
            f"/internal/stamps/{valid_address}",
            json=valid_payload,
            headers={"HTTP_AUTHORIZATION": "invalid_key"},
        )
        assert response.status_code == 401
        assert "Unauthorized" in response.json()["detail"]

    @pytest.mark.parametrize(
        "invalid_address",
        [
            pytest.param("invalid_address", id="invalid-format"),
            pytest.param("0x123", id="too-short"),
            pytest.param("0x" + "1" * 41, id="too-long"),
            pytest.param("0xGGGG", id="invalid-hex"),
            pytest.param("", id="empty"),
        ],
    )
    def test_invalid_addresses(self, client, invalid_address, valid_payload):
        """Test various invalid address formats"""
        with pytest.raises(InvalidAddressException):
            client.post(
                f"/internal/stamps/{invalid_address}",
                json=valid_payload,
                headers={"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
            )

    def test_empty_stamps_list(self, client, valid_address):
        """Test payload with empty stamps list"""
        payload = {"scorer_id": 1, "stamps": []}

        response = client.post(
            f"/internal/stamps/{valid_address}",
            json=payload,
            headers={"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        assert response.status_code == 400
        assert "stamps list cannot be empty" in response.json()["detail"]

    @pytest.mark.parametrize(
        "invalid_field",
        [
            pytest.param({"scorer_id": "not_an_int"}, id="invalid-scorer-id-type"),
            pytest.param({"scorer_id": -1}, id="negative-scorer-id"),
            pytest.param({"scorer_id": None}, id="null-scorer-id"),
            pytest.param({"stamps": None}, id="null-stamps"),
            pytest.param({"stamps": "not_a_list"}, id="invalid-stamps-type"),
        ],
    )
    def test_invalid_payload_fields(
        self, client, valid_address, valid_payload, invalid_field
    ):
        """Test various invalid payload fields"""
        invalid_payload = {**valid_payload, **invalid_field}
        response = client.post(
            f"/internal/stamps/{valid_address}",
            json=invalid_payload,
            headers={"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )
        assert response.status_code == 422  # Validation error

    @patch("ceramic_cache.api.v1.handle_add_stamps")
    def test_successful_stamp_addition(
        self,
        mock_handle_add_stamps,
        client,
        valid_address,
        valid_payload,
        mock_success_response,
    ):
        """Test successful stamp addition with detailed response validation"""
        mock_handle_add_stamps.return_value = mock_success_response

        response = client.post(
            f"/internal/stamps/{valid_address}",
            json=valid_payload,
            headers={"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )

        assert response.status_code == 201
        response_data = response.json()

        # Verify response structure
        assert response_data["success"] is True
        assert len(response_data["stamps"]) == 1

        # Verify stamp details
        stamp = response_data["stamps"][0]
        assert stamp["provider"] == "github"
        assert stamp["address"] == valid_address
        assert "id" in stamp
        assert "stamp" in stamp

        # Verify score details
        score = response_data["score"]
        assert isinstance(score["score"], float)
        assert score["status"] == "DONE"
        assert "stats" in score
        assert "provider_stats" in score["stats"]
        assert "github" in score["stats"]["provider_stats"]

        # Verify handle_add_stamps was called correctly
        mock_handle_add_stamps.assert_called_once()
        called_address, called_stamps, called_scorer_id = (
            mock_handle_add_stamps.call_args[0]
        )
        assert called_address == valid_address.lower()
        assert isinstance(called_stamps[0], CacheStampPayload)
        assert called_scorer_id == valid_payload["scorer_id"]

    @patch("ceramic_cache.api.v1.handle_add_stamps")
    def test_handles_database_errors(
        self, mock_handle_add_stamps, client, valid_address, valid_payload
    ):
        """Test handling of database errors"""
        mock_handle_add_stamps.side_effect = Exception("Database error")

        response = client.post(
            f"/internal/stamps/{valid_address}",
            json=valid_payload,
            headers={"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN},
        )

        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
