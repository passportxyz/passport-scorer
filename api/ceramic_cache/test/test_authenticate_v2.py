"""
Tests for the /ceramic-cache/authenticate/v2 endpoint (SIWE-based authentication)
"""
import json
from unittest.mock import Mock, patch

import pytest
from django.test import Client
from ninja_jwt.tokens import AccessToken
from web3 import Web3

from account.models import Nonce

pytestmark = pytest.mark.django_db

client = Client()


# Sample SIWE message for testing
def create_siwe_message(address: str, nonce: str) -> dict:
    """Create a valid SIWE message dict"""
    return {
        "domain": "app.passport.xyz",
        "address": address,
        "statement": "Sign in to Human Passport",
        "uri": "https://app.passport.xyz",
        "version": "1",
        "chainId": 1,
        "nonce": nonce,
        "issuedAt": "2024-01-01T00:00:00.000Z"
    }


class TestAuthenticateV2EOA:
    """Tests for EOA (Externally Owned Account) authentication"""
    base_url = "/ceramic-cache"

    def test_successful_eoa_authentication(self, mocker):
        """Test successful EOA authentication with valid SIWE signature"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock is_smart_wallet to return False (EOA)
        mocker.patch("ceramic_cache.api.v1.is_smart_wallet", return_value=False)

        # Mock SIWE verification
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"
        mock_instance.verify = Mock()  # Successful verification (no exception)

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        json_data = response.json()

        # Check response structure (no intercom_user_hash in v2)
        assert "access" in json_data
        assert "intercom_user_hash" not in json_data

        # Verify JWT contains correct DID (always eip155:1)
        token = AccessToken(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

    def test_invalid_nonce_rejection(self, mocker):
        """Test that invalid/expired nonce is rejected"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"

        payload = {
            "message": create_siwe_message(test_address, "invalid-nonce-123"),
            "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "detail" in json_data
        assert "Invalid nonce" in json_data["detail"]

    def test_invalid_signature_rejection(self, mocker):
        """Test that invalid EOA signature is rejected"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock is_smart_wallet to return False (EOA)
        mocker.patch("ceramic_cache.api.v1.is_smart_wallet", return_value=False)

        # Mock SIWE verification to raise exception (invalid signature)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.verify.side_effect = Exception("Invalid signature")

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0xbadsignature1234567890abcdef1234567890abcdef1234567890abcdef12345678"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "detail" in json_data
        assert "Invalid signature" in json_data["detail"]

    def test_nonce_can_only_be_used_once(self, mocker):
        """Test that nonce can only be used once"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock is_smart_wallet to return False (EOA)
        mocker.patch("ceramic_cache.api.v1.is_smart_wallet", return_value=False)

        # Mock SIWE verification
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.verify = Mock()

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
        }

        # First request should succeed
        response1 = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )
        assert response1.status_code == 200

        # Second request with same nonce should fail
        response2 = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )
        assert response2.status_code == 400
        json_data = response2.json()
        assert "Invalid nonce" in json_data["detail"]


class TestAuthenticateV2SmartWallet:
    """Tests for smart contract wallet (EIP-1271) authentication"""
    base_url = "/ceramic-cache"

    def test_successful_smart_wallet_authentication(self, mocker):
        """Test successful smart wallet authentication via EIP-1271"""
        # Using a known smart wallet address (example)
        test_address = "0x4bBa290826C253BD854121346c370a9886d1bC26"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock is_smart_wallet to return True
        mocker.patch("ceramic_cache.api.v1.is_smart_wallet", return_value=True)

        # Mock EIP-1271 verification to return True
        mocker.patch("ceramic_cache.api.v1.verify_eip1271_signature", return_value=True)

        # Mock SiweMessage for preparing the message
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        json_data = response.json()

        # Check response structure
        assert "access" in json_data
        assert "intercom_user_hash" not in json_data

        # Verify JWT contains correct DID
        token = AccessToken(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

    def test_smart_wallet_invalid_signature(self, mocker):
        """Test that invalid smart wallet signature is rejected"""
        test_address = "0x4bBa290826C253BD854121346c370a9886d1bC26"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock is_smart_wallet to return True
        mocker.patch("ceramic_cache.api.v1.is_smart_wallet", return_value=True)

        # Mock EIP-1271 verification to return False (invalid signature)
        mocker.patch("ceramic_cache.api.v1.verify_eip1271_signature", return_value=False)

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0xbadsignature"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "detail" in json_data
        assert "Invalid signature" in json_data["detail"]


class TestAuthenticateV2EdgeCases:
    """Test edge cases and validation"""
    base_url = "/ceramic-cache"

    def test_missing_address_in_message(self):
        """Test that missing address is rejected"""
        nonce_obj = Nonce.create_nonce(ttl=300)

        payload = {
            "message": {
                "domain": "app.passport.xyz",
                # address is missing
                "nonce": nonce_obj.nonce,
            },
            "signature": "0x1234"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "Missing address or nonce" in json_data["detail"]

    def test_missing_nonce_in_message(self):
        """Test that missing nonce is rejected"""
        payload = {
            "message": {
                "domain": "app.passport.xyz",
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
                # nonce is missing
            },
            "signature": "0x1234"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "Missing address or nonce" in json_data["detail"]


class TestOldEndpointStillWorks:
    """Regression test: ensure old /authenticate endpoint still works"""
    base_url = "/ceramic-cache"

    def test_old_authenticate_endpoint_still_works(self, mocker):
        """Test that the original /authenticate endpoint with DagJWS still works"""
        # This is a regression test to ensure we didn't break the old endpoint

        sample_payload = {
            "signatures": [{
                "protected": "eyJhbGciOiJFZERTQSIsImNhcCI6ImlwZnM6Ly9iYWZ5cmVpZmhkYTQ2eWp5NWRhYWxocXh2anZvcnpqdnlleHp1bjRrcWRmZWU0YnkybmJyNWhzcHd1eSIsImtpZCI6ImRpZDprZXk6ejZNa2pHSGtRNDVpY3BSakdqWUhWWUZLTkpDMTdwbnE0UU04UWJuODhLSEVaQ05XI3o2TWtqR0hrUTQ1aWNwUmpHallIVllGS05KQzE3cG5xNFFNOFFibjg4S0hFWkNOVyJ9",
                "signature": "UmVH-NMdgn-P-VE0ejTlmrRxbF45W20Q9SfIThqODF9USwzxFi3kceDttlBWwNZkrGogdqm-SdJQdoRC0GYSCA",
            }],
            "payload": "AXESIJ-t3oi3FWOnXzz1JomHf4BeT-DVOaW5-RtZGPf_miHs",
            "cid": [1, 113, 18],
            "cacao": [163, 97, 104],
            "issuer": "did:pkh:eip155:1:0xffffffffffffffffffffffffffffffffffffffff",
            "nonce": Nonce.create_nonce().nonce,
        }

        # Mock the verifier response
        class MockedRequestResponse:
            status_code = 200
            def json(self):
                return {"status": "ok"}

        mocker.patch("ceramic_cache.api.v1.requests.post", return_value=MockedRequestResponse())
        mocker.patch("ceramic_cache.api.v1.validate_dag_jws_payload", return_value=True)

        response = client.post(
            f"{self.base_url}/authenticate",
            json.dumps(sample_payload),
            content_type="application/json",
        )

        # Old endpoint should still work and return access token
        assert response.status_code == 200
        json_data = response.json()
        assert "access" in json_data
