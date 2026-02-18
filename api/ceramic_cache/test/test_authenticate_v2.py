"""
Tests for the /ceramic-cache/authenticate/v2 endpoint (SIWE-based authentication)
Uses ERC-6492 Universal Signature Validator for all signature types (EOA + smart wallets)
"""

import json
from unittest.mock import Mock

import jwt
import pytest
from django.conf import settings
from django.test import Client

from account.models import Nonce

pytestmark = pytest.mark.django_db

client = Client()


def decode_siwe_jwt(token: str) -> dict:
    """Decode an RS256 JWT using the test public key from settings"""
    return jwt.decode(token, settings.SIWE_JWT_PUBLIC_KEY, algorithms=["RS256"])


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
        "issuedAt": "2024-01-01T00:00:00.000Z",
    }


class TestAuthenticateV2:
    """Tests for SIWE authentication using ERC-6492 universal signature verification"""

    base_url = "/ceramic-cache"

    def test_successful_authentication(self, mocker):
        """Test successful authentication with valid signature (ERC-6492)"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
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
            "signature": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12",
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
        # v2 auth does not include intercom_user_hash (it's None or not present)
        assert json_data.get("intercom_user_hash") is None

        # Verify JWT contains correct DID (always eip155:1)
        token = decode_siwe_jwt(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

    def test_successful_authentication_on_base(self, mocker):
        """Test successful authentication on Base chain (chainId 8453)

        Note: ERC-6492 verification always uses mainnet (chain_id=1) since smart wallet
        factories are deployed on 100+ chains including mainnet. The SIWE message chain_id
        is preserved for the user's intent but verification uses mainnet for simplicity.
        """
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification
        mock_verify = mocker.patch(
            "ceramic_cache.api.v1.verify_signature_erc6492", return_value=True
        )

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(
                test_address, nonce_obj.nonce, chain_id=8453
            ),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        # Verify ERC-6492 was called with mainnet (always chain_id=1)
        mock_verify.assert_called_once()
        call_args = mock_verify.call_args
        assert call_args[0][3] == 1  # verification always uses mainnet

        # DID should still use eip155:1 (identifier format, not verification chain)
        json_data = response.json()
        token = decode_siwe_jwt(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

    def test_invalid_nonce_rejection(self):
        """Test that invalid/expired nonce is rejected"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"

        payload = {
            "message": create_siwe_message(test_address, "invalid-nonce-123"),
            "signature": "0x1234",
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
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification to return False (invalid signature)
        mocker.patch(
            "ceramic_cache.api.v1.verify_signature_erc6492", return_value=False
        )

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0xbadsignature",
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
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
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
            "signature": "0x1234",
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
        """Test smart wallet authentication on Base chain (e.g., Coinbase Smart Wallet)

        Note: ERC-6492 verification always uses mainnet (chain_id=1) since smart wallet
        factories are deployed on 100+ chains including mainnet.
        """
        # Coinbase Smart Wallet example address
        test_address = "0x4bBa290826C253BD854121346c370a9886d1bC26"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification - handles smart wallets automatically
        mock_verify = mocker.patch(
            "ceramic_cache.api.v1.verify_signature_erc6492", return_value=True
        )

        # Mock SiweMessage
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(
                test_address, nonce_obj.nonce, chain_id=8453
            ),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        json_data = response.json()

        # Verify JWT contains correct DID
        token = decode_siwe_jwt(json_data["access"])
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did

        # Verify ERC-6492 was called with mainnet (always chain_id=1)
        mock_verify.assert_called_once()
        call_args = mock_verify.call_args
        assert call_args[0][3] == 1  # verification always uses mainnet


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
            "signature": "0x1234",
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
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            },
            "signature": "0x1234",
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
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mock_verify = mocker.patch(
            "ceramic_cache.api.v1.verify_signature_erc6492", return_value=True
        )

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
                "issuedAt": "2024-01-01T00:00:00.000Z",
            },
            "signature": "0x1234",
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


class TestJWTTokenStructure:
    """Test RS256 JWT token structure and claims"""

    base_url = "/ceramic-cache"

    def test_jwt_contains_required_claims(self, mocker):
        """Test that JWT contains all required claims: did, iat, exp, jti, iss, token_type"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        token = decode_siwe_jwt(response.json()["access"])

        # Check all required claims exist
        assert "did" in token
        assert "iat" in token
        assert "exp" in token
        assert "jti" in token
        assert "iss" in token
        assert "token_type" in token

        # Check values
        assert token["iss"] == "passport-scorer"
        assert token["token_type"] == "access"
        assert token["exp"] > token["iat"]  # exp must be after iat

    def test_address_is_normalized_to_lowercase(self, mocker):
        """Test that address is normalized to lowercase in DID"""
        # Use uppercase address
        test_address = "0x742D35CC6634C0532925A3B844BC9E7595F0BEB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        token = decode_siwe_jwt(response.json()["access"])

        # DID should have lowercase address
        expected_did = f"did:pkh:eip155:1:{test_address.lower()}"
        assert token["did"] == expected_did


class TestMultiChainSupport:
    """Test support for SIWE messages from multiple L2 chains.

    Note: ERC-6492 verification always uses mainnet (chain_id=1) since smart wallet
    factories are deployed on 100+ chains including mainnet. The SIWE message's chainId
    is accepted and preserved for user intent, but verification is done against mainnet.
    """

    base_url = "/ceramic-cache"

    def test_authentication_on_arbitrum(self, mocker):
        """Test authentication with Arbitrum chainId in SIWE message (42161)"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mock_verify = mocker.patch(
            "ceramic_cache.api.v1.verify_signature_erc6492", return_value=True
        )
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(
                test_address, nonce_obj.nonce, chain_id=42161
            ),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        # Verify ERC-6492 was called with mainnet (always chain_id=1)
        mock_verify.assert_called_once()
        call_args = mock_verify.call_args
        assert call_args[0][3] == 1  # verification always uses mainnet

    def test_authentication_on_optimism(self, mocker):
        """Test authentication with Optimism chainId in SIWE message (10)"""
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mock_verify = mocker.patch(
            "ceramic_cache.api.v1.verify_signature_erc6492", return_value=True
        )
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce, chain_id=10),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        mock_verify.assert_called_once()
        assert mock_verify.call_args[0][3] == 1  # verification always uses mainnet


class TestRS256TokenOnProtectedEndpoints:
    """Integration tests: verify RS256 tokens from /authenticate/v2 work on protected endpoints"""

    base_url = "/ceramic-cache"

    def test_rs256_token_works_on_score_endpoint(self, mocker):
        """
        End-to-end test: get RS256 token from /authenticate/v2,
        then use it on /ceramic-cache/score/{address}
        """
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Mock ERC-6492 verification for auth
        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        # Step 1: Get RS256 token from /authenticate/v2
        auth_payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        auth_response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(auth_payload),
            content_type="application/json",
        )

        assert auth_response.status_code == 200
        rs256_token = auth_response.json()["access"]

        # Verify it's actually an RS256 token
        header = jwt.get_unverified_header(rs256_token)
        assert header["alg"] == "RS256", f"Expected RS256 token, got {header['alg']}"

        # Step 2: Use the RS256 token on a protected endpoint
        # The score endpoint should accept the token (even if no score exists)
        score_response = client.get(
            f"{self.base_url}/score/{test_address.lower()}",
            HTTP_AUTHORIZATION=f"Bearer {rs256_token}",
        )

        # Should NOT be 401 Unauthorized - the token should be accepted
        # (may be 404 if no passport exists, but that's fine - auth worked)
        assert score_response.status_code != 401, (
            f"RS256 token was rejected with 401. Response: {score_response.json()}"
        )

    def test_hs256_token_still_works_on_score_endpoint(self, mocker):
        """
        Regression test: HS256 tokens from old /authenticate endpoint
        should still work on protected endpoints
        """
        test_address = "0xffffffffffffffffffffffffffffffffffffffff"

        # Create an HS256 token using the old method (ninja_jwt)
        from ceramic_cache.api.v1 import generate_access_token_response

        hs256_response = generate_access_token_response(
            f"did:pkh:eip155:1:{test_address}"
        )
        hs256_token = hs256_response.access

        # Verify it's actually an HS256 token
        header = jwt.get_unverified_header(hs256_token)
        assert header["alg"] == "HS256", f"Expected HS256 token, got {header['alg']}"

        # Use the HS256 token on a protected endpoint
        score_response = client.get(
            f"{self.base_url}/score/{test_address}",
            HTTP_AUTHORIZATION=f"Bearer {hs256_token}",
        )

        # Should NOT be 401 Unauthorized
        assert score_response.status_code != 401, (
            f"HS256 token was rejected with 401. Response: {score_response.json()}"
        )


class TestVerifySignatureERC6492:
    """
    Unit tests for verify_signature_erc6492 function.

    These tests mock at the Web3 level (not the function level) to ensure
    the function internals are exercised and bugs like incorrect imports
    are caught.
    """

    def test_valid_signature_returns_true(self, mocker):
        """Test that valid signature verification returns True"""
        from ceramic_cache.api.v1 import verify_signature_erc6492

        # Mock get_web3_for_chain to return a mock Web3 instance
        mock_w3 = Mock()
        # Mock codec.encode to return actual bytes (ABI-encoded params)
        mock_w3.codec.encode.return_value = b"\x00" * 128
        # Mock eth.call to return 0x01 (valid signature)
        mock_w3.eth.call.return_value = b"\x01"

        mocker.patch("ceramic_cache.api.v1.get_web3_for_chain", return_value=mock_w3)

        result = verify_signature_erc6492(
            address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            message_hash=b"\x00" * 32,
            signature="0x" + "00" * 65,
            chain_id=1,
        )

        assert result is True
        mock_w3.eth.call.assert_called_once()

    def test_invalid_signature_returns_false(self, mocker):
        """Test that invalid signature verification returns False"""
        from ceramic_cache.api.v1 import verify_signature_erc6492

        mock_w3 = Mock()
        # Mock codec.encode to return actual bytes
        mock_w3.codec.encode.return_value = b"\x00" * 128
        # Mock eth.call to return 0x00 (invalid signature)
        mock_w3.eth.call.return_value = b"\x00"

        mocker.patch("ceramic_cache.api.v1.get_web3_for_chain", return_value=mock_w3)

        result = verify_signature_erc6492(
            address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            message_hash=b"\x00" * 32,
            signature="0x" + "00" * 65,
            chain_id=1,
        )

        assert result is False

    def test_web3_exception_returns_false(self, mocker):
        """Test that Web3 exceptions are caught and return False"""
        from ceramic_cache.api.v1 import verify_signature_erc6492

        mock_w3 = Mock()
        # Mock codec.encode to return actual bytes
        mock_w3.codec.encode.return_value = b"\x00" * 128
        # Mock eth.call to raise an exception (RPC error)
        mock_w3.eth.call.side_effect = Exception("RPC error")

        mocker.patch("ceramic_cache.api.v1.get_web3_for_chain", return_value=mock_w3)

        result = verify_signature_erc6492(
            address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            message_hash=b"\x00" * 32,
            signature="0x" + "00" * 65,
            chain_id=1,
        )

        assert result is False

    def test_uses_correct_chain_id(self, mocker):
        """Test that the correct chain ID is passed to get_web3_for_chain"""
        from ceramic_cache.api.v1 import verify_signature_erc6492

        mock_w3 = Mock()
        # Mock codec.encode to return actual bytes
        mock_w3.codec.encode.return_value = b"\x00" * 128
        # Mock eth.call to return valid signature
        mock_w3.eth.call.return_value = b"\x01"

        mock_get_web3 = mocker.patch(
            "ceramic_cache.api.v1.get_web3_for_chain", return_value=mock_w3
        )

        # Test with Base chain ID
        verify_signature_erc6492(
            address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            message_hash=b"\x00" * 32,
            signature="0x" + "00" * 65,
            chain_id=8453,
        )

        mock_get_web3.assert_called_once_with(8453)

    def test_signature_without_0x_prefix(self, mocker):
        """Test that signatures without 0x prefix are handled correctly"""
        from ceramic_cache.api.v1 import verify_signature_erc6492

        mock_w3 = Mock()
        # Mock codec.encode to return actual bytes
        mock_w3.codec.encode.return_value = b"\x00" * 128
        # Mock eth.call to return valid signature
        mock_w3.eth.call.return_value = b"\x01"

        mocker.patch("ceramic_cache.api.v1.get_web3_for_chain", return_value=mock_w3)

        # Signature without 0x prefix should still work
        result = verify_signature_erc6492(
            address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            message_hash=b"\x00" * 32,
            signature="00" * 65,  # No 0x prefix
            chain_id=1,
        )

        assert result is True


class TestGetWeb3ForChain:
    """
    Unit tests for get_web3_for_chain function.

    Tests the RPC URL construction for different chains.
    """

    def test_returns_web3_instance_for_mainnet(self, mocker):
        """Test that mainnet returns a Web3 instance with correct RPC URL"""
        from ceramic_cache.api.v1 import get_web3_for_chain

        # Mock Web3 to capture the provider URL
        mock_web3_class = mocker.patch("ceramic_cache.api.v1.Web3")

        get_web3_for_chain(1)

        # Verify HTTPProvider was called (via Web3.HTTPProvider)
        mock_web3_class.HTTPProvider.assert_called_once()
        call_args = mock_web3_class.HTTPProvider.call_args
        rpc_url = call_args[0][0]
        assert "eth-mainnet" in rpc_url
        assert "alchemy.com" in rpc_url

    def test_returns_web3_instance_for_base(self, mocker):
        """Test that Base chain returns correct RPC URL"""
        from ceramic_cache.api.v1 import get_web3_for_chain

        mock_web3_class = mocker.patch("ceramic_cache.api.v1.Web3")

        get_web3_for_chain(8453)

        call_args = mock_web3_class.HTTPProvider.call_args
        rpc_url = call_args[0][0]
        assert "base-mainnet" in rpc_url

    def test_unknown_chain_falls_back_to_mainnet(self, mocker):
        """Test that unknown chain IDs fall back to mainnet"""
        from ceramic_cache.api.v1 import get_web3_for_chain

        mock_web3_class = mocker.patch("ceramic_cache.api.v1.Web3")

        # Use an unsupported chain ID
        get_web3_for_chain(999999)

        call_args = mock_web3_class.HTTPProvider.call_args
        rpc_url = call_args[0][0]
        assert "eth-mainnet" in rpc_url


class TestDomainValidation:
    """Tests for SIWE domain validation on the /authenticate/v2 endpoint.

    Domain validation must happen BEFORE nonce consumption so that an attacker
    cannot burn a user's nonce by sending a request with a spoofed domain.
    """

    base_url = "/ceramic-cache"

    def test_valid_domain_passes_authentication(self, mocker, settings):
        """Test that a valid domain in the allowlist passes authentication"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert "access" in response.json()

    def test_invalid_domain_is_rejected(self, settings):
        """Test that a domain not in the allowlist is rejected with 400"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_siwe_message(test_address, nonce_obj.nonce)
        message["domain"] = "evil.com"

        payload = {
            "message": message,
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "detail" in json_data

    def test_invalid_domain_does_not_consume_nonce(self, settings):
        """Test that a rejected domain does NOT consume the nonce.

        This is critical: domain validation must happen BEFORE nonce consumption
        so an attacker cannot burn valid nonces with spoofed-domain requests.
        """
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_siwe_message(test_address, nonce_obj.nonce)
        message["domain"] = "evil.com"

        payload = {
            "message": message,
            "signature": "0x1234",
        }

        # First request with bad domain should fail
        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

        # The nonce should still be valid (not consumed)
        assert Nonce.use_nonce(nonce_obj.nonce) is True

    def test_missing_domain_is_rejected(self, settings):
        """Test that a missing domain is rejected"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_siwe_message(test_address, nonce_obj.nonce)
        del message["domain"]

        payload = {
            "message": message,
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_empty_allowlist_rejects_all(self, settings):
        """Test that an empty allowlist rejects all domains (fail closed)"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = []

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_domain_matching_is_case_insensitive(self, mocker, settings):
        """Test that domain matching is case-insensitive"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        message = create_siwe_message(test_address, nonce_obj.nonce)
        message["domain"] = "APP.PASSPORT.XYZ"

        payload = {
            "message": message,
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert "access" in response.json()


class TestExpirationValidation:
    """Tests for SIWE expiration validation on the /authenticate/v2 endpoint.

    Expiration validation must happen BEFORE nonce consumption so that an attacker
    cannot burn a user's nonce by replaying an expired SIWE message.
    """

    base_url = "/ceramic-cache"

    def test_expired_message_is_rejected(self, settings):
        """Test that an expired SIWE message is rejected with 400"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_siwe_message(test_address, nonce_obj.nonce)
        message["expirationTime"] = "2020-01-01T00:00:00.000Z"

        payload = {
            "message": message,
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        json_data = response.json()
        assert "detail" in json_data

    def test_valid_future_expiration_passes(self, mocker, settings):
        """Test that a SIWE message with future expiration passes"""
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        message = create_siwe_message(test_address, nonce_obj.nonce)
        message["expirationTime"] = "2099-12-31T23:59:59.000Z"

        payload = {
            "message": message,
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert "access" in response.json()

    def test_no_expiration_passes(self, mocker, settings):
        """Test that a SIWE message without expirationTime passes (backwards compatible).

        Messages without expirationTime should still be accepted since nonce TTL
        provides time-bounding. This maintains backwards compatibility.
        """
        settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        mocker.patch("ceramic_cache.api.v1.verify_signature_erc6492", return_value=True)
        mock_siwe = mocker.patch("ceramic_cache.api.v1.SiweMessage")
        mock_instance = Mock()
        mock_siwe.return_value = mock_instance
        mock_instance.prepare_message.return_value = "SIWE message text"

        # create_siwe_message() does NOT include expirationTime by default
        payload = {
            "message": create_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            f"{self.base_url}/authenticate/v2",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert "access" in response.json()
