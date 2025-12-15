"""
Tests for the /ceramic-cache/authenticate/v2 endpoint (SIWE-based authentication)
Uses ERC-6492 Universal Signature Validator for all signature types (EOA + smart wallets)
"""
import json
from unittest.mock import Mock

import pytest
from django.test import Client
from ninja_jwt.tokens import AccessToken

from account.models import Nonce

pytestmark = pytest.mark.django_db

client = Client()


def create_siwe_message(address: str, nonce: str, chain_id: int = 1) -> dict:
    """Create a valid SIWE message dict"""
    return {
        "domain": "app.passport.xyz",
        "address": address,
        "statement": "Sign in to Human Passport",
        "uri": "https://app.passport.xyz",
        "version": "1",
        "chainId": chain_id,
        "nonce": nonce,
        "issuedAt": "2024-01-01T00:00:00.000Z"
    }


class TestAuthenticateV2:
    """Tests for SIWE authentication using ERC-6492 universal signature verification"""
    base_url = "/ceramic-cache"

    def test_successful_authentication(self, mocker):
        """Test successful authentication with valid signature (ERC-6492)"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification to return True
        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)

        # Mock SiweMessage
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

        # Verify JWT contains correct DID (always eip155:1)
        token = AccessToken(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

    def test_successful_authentication_on_base(self, mocker):
        """Test successful authentication on Base chain (chainId 8453)"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification
        mock_verify = mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce, chain_id=8453),
            "signature": "0x1234"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        # Verify ERC-6492 was called with correct chain_id
        mock_verify.assert_called_once()
        call_args = mock_verify.call_args
        assert call_args[0][3] == 8453  # chain_id is the 4th argument

        # DID should still use eip155:1 (identifier format, not verification chain)
        json_data = response.json()
        token = AccessToken(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

    def test_invalid_nonce_rejection(self):
        """Test that invalid/expired nonce is rejected"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"

        payload = {
            "message": create_siwe_message(test_address, "invalid-nonce-123"),
            "signature": "0x1234"
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
        """Test that invalid signature is rejected"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification to return False (invalid signature)
        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=False)

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

    def test_nonce_can_only_be_used_once(self, mocker):
        """Test that nonce can only be used once"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification
        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234"
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

    def test_smart_wallet_on_base(self, mocker):
        """Test smart wallet authentication on Base chain (e.g., Coinbase Smart Wallet)"""
        # Coinbase Smart Wallet example address
        test_address = "0x4bBa290826C253BD854121346c370a9886d1bC26"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification - handles smart wallets automatically
        mock_verify = mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce, chain_id=8453),
            "signature": "0x1234"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        json_data = response.json()

        # Verify JWT contains correct DID
        token = AccessToken(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

        # Verify ERC-6492 was called with Base chain
        mock_verify.assert_called_once()
        call_args = mock_verify.call_args
        assert call_args[0][3] == 8453


class TestAuthenticateV2EdgeCases:
    """Test edge cases and validation"""
    base_url = "/ceramic-cache"

    def test_missing_address_in_message(self):
        """Test that missing address is rejected"""
        nonce_obj = Nonce.create_nonce(ttl=300)

        payload = {
            "message": {
                "domain": "app.passport.xyz",
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

    def test_defaults_to_mainnet_when_chain_not_specified(self, mocker):
        """Test that chainId defaults to 1 (mainnet) when not specified"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mock_verify = mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)

        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        # Message without chainId
        payload = {
            "message": {
                "domain": "app.passport.xyz",
                "address": test_address,
                "statement": "Sign in",
                "uri": "https://app.passport.xyz",
                "version": "1",
                "nonce": nonce_obj.nonce,
                "issuedAt": "2024-01-01T00:00:00.000Z"
            },
            "signature": "0x1234"
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        # Verify ERC-6492 was called with mainnet (chain_id=1)
        mock_verify.assert_called_once()
        call_args = mock_verify.call_args
        assert call_args[0][3] == 1


class TestOldEndpointStillWorks:
    """Regression test: ensure old /authenticate endpoint still works"""
    base_url = "/ceramic-cache"

    def test_old_authenticate_endpoint_still_works(self, mocker):
        """Test that the original /authenticate endpoint with DagJWS still works"""
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

        assert response.status_code == 200
        json_data = response.json()
        assert "access" in json_data
