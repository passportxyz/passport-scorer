import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.conf import settings

from ceramic_cache.api.schema import (
    CacheStampPayload,
    DetailedScoreResponse,
    GetStampsWithScoreResponse,
)
from registry.api.schema import StatusEnum, ThresholdScoreEvidenceResponse


@pytest.fixture
def valid_address():
    return "0x394EFd95c167fF30EE8668C24B281487f43D2122"


@pytest.fixture
def sample_credential(valid_address):
    now = datetime.now(timezone.utc)
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
def valid_payload(sample_credential, scorer_community_with_binary_scorer):
    return {
        "scorer_id": scorer_community_with_binary_scorer.pk,
        "stamps": [sample_credential],
    }


future_expiration_date = datetime.now(timezone.utc) + timedelta(days=5)


@pytest.fixture
def mock_success_handle_add_stamps(valid_address, sample_credential):
    return GetStampsWithScoreResponse(
        stamps=[
            {
                "id": 0,
                "address": valid_address.lower(),
                "provider": sample_credential["credentialSubject"]["provider"],
                "stamp": sample_credential,
            }
        ],
        success=True,
        score=DetailedScoreResponse(
            address=valid_address.lower(),
            score="1.000000000",
            status=StatusEnum.done,
            last_score_timestamp=future_expiration_date.isoformat(),
            expiration_date=future_expiration_date.isoformat(),
            error=None,
            stamp_scores={},
            evidence=ThresholdScoreEvidenceResponse(
                rawScore=7.0,
                threshold=5.0,
                success=True,
                type="binary",
            ),
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
            json.dumps(valid_payload),
            HTTP_AUTHORIZATION="invalid_token",
            content_type="application/json",
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
        ],
    )
    def test_invalid_addresses(self, client, invalid_address, valid_payload):
        """Test various invalid address formats"""
        response = client.post(
            f"/internal/stamps/{invalid_address}",
            json.dumps(valid_payload),
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
            content_type="application/json",
        )
        assert "Invalid address." in response.json()["detail"]
        assert response.status_code == 400

    def test_empty_stamps_list(
        self, client, valid_address, scorer_community_with_binary_scorer
    ):
        """Test payload with empty stamps list"""
        payload = {"scorer_id": scorer_community_with_binary_scorer.pk, "stamps": []}

        response = client.post(
            f"/internal/stamps/{valid_address}",
            json.dumps(payload),
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
            content_type="application/json",
        )
        assert response.status_code == 200

        response_data = response.json()

        assert response_data["success"] is True
        assert len(response_data["stamps"]) == 0

        # Verify score details
        score = response_data["score"]
        assert score["error"] is None
        assert isinstance(score["score"], str)
        assert int(float(score["score"])) == 0

    @pytest.mark.parametrize(
        "invalid_field",
        [
            pytest.param({"scorer_id": "not_an_int"}, id="invalid-scorer-id-type"),
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
            json.dumps(invalid_payload),
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
            content_type="application/json",
        )
        assert response.status_code == 422  # Validation error

    @patch("internal.api.handle_add_stamps")
    def test_successful_stamp_addition(
        self,
        mock_handle_add_stamps,
        client,
        valid_address,
        valid_payload,
        mock_success_handle_add_stamps,
    ):
        """Test successful stamp addition with detailed response validation"""
        mock_handle_add_stamps.return_value = mock_success_handle_add_stamps

        response = client.post(
            f"/internal/stamps/{valid_address}",
            json.dumps(valid_payload),
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
            content_type="application/json",
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert response_data["success"] is True
        assert len(response_data["stamps"]) == 1

        # Verify stamp details
        stamp = response_data["stamps"][0]
        assert stamp["provider"] == "github"
        assert stamp["address"] == valid_address.lower()
        assert "id" in stamp
        assert "stamp" in stamp

        # Verify score details
        score = response_data["score"]
        assert score["error"] is None
        assert isinstance(score["score"], str)
        assert int(float(score["score"])) == 1

        # Verify handle_add_stamps was called correctly
        mock_handle_add_stamps.assert_called_once()
        called_address, called_stamps, called_scorer_id = (
            mock_handle_add_stamps.call_args[0]
        )
        assert called_address.lower() == valid_address.lower()
        assert isinstance(called_stamps[0], CacheStampPayload)
        assert called_scorer_id == valid_payload["scorer_id"]
