"""
Tests for domain and expiration validation on the /account/verify endpoint.

Domain and expiration validation must happen BEFORE nonce consumption so that
an attacker cannot burn a user's nonce by sending spoofed/expired messages.
"""

import json

import pytest
from django.test import Client

from account.models import Nonce

pytestmark = pytest.mark.django_db

client = Client()


def create_account_siwe_message(address: str, nonce: str, chain_id: int = 1) -> dict:
    """Create a valid SIWE message dict for the /account/verify endpoint."""
    return {
        "domain": "localhost",
        "address": address,
        "statement": "Sign in with Ethereum to the app.",
        "uri": "http://localhost",
        "version": "1",
        "chainId": chain_id,
        "nonce": nonce,
        "issuedAt": "2024-01-01T00:00:00.000Z",
    }


class TestAccountDomainValidation:
    """Tests for SIWE domain validation on the /account/verify endpoint."""

    def test_invalid_domain_is_rejected(self, settings):
        """Test that a domain not in SIWE_ALLOWED_DOMAINS_ACCOUNT is rejected"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost", "localhost:3000"]
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_account_siwe_message(test_address, nonce_obj.nonce)
        message["domain"] = "evil.com"

        payload = {"message": message, "signature": "0x1234"}

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_invalid_domain_does_not_consume_nonce(self, settings):
        """Test that rejected domain does NOT consume the nonce (pre-nonce validation)"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost", "localhost:3000"]
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_account_siwe_message(test_address, nonce_obj.nonce)
        message["domain"] = "evil.com"

        payload = {"message": message, "signature": "0x1234"}

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

        # The nonce should still be valid (not consumed)
        assert Nonce.use_nonce(nonce_obj.nonce) is True

    def test_missing_domain_is_rejected(self, settings):
        """Test that a missing domain is rejected"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost"]
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_account_siwe_message(test_address, nonce_obj.nonce)
        del message["domain"]

        payload = {"message": message, "signature": "0x1234"}

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_empty_allowlist_rejects_all(self, settings):
        """Test that an empty allowlist rejects all domains (fail closed)"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = []
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        payload = {
            "message": create_account_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400


class TestAccountExpirationValidation:
    """Tests for SIWE expiration validation on the /account/verify endpoint."""

    def test_expired_message_is_rejected(self, settings):
        """Test that an expired SIWE message is rejected"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost"]
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_account_siwe_message(test_address, nonce_obj.nonce)
        message["expirationTime"] = "2020-01-01T00:00:00.000Z"

        payload = {"message": message, "signature": "0x1234"}

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_expired_message_does_not_consume_nonce(self, settings):
        """Test that an expired message does NOT consume the nonce"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost"]
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        message = create_account_siwe_message(test_address, nonce_obj.nonce)
        message["expirationTime"] = "2020-01-01T00:00:00.000Z"

        payload = {"message": message, "signature": "0x1234"}

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

        # The nonce should still be valid
        assert Nonce.use_nonce(nonce_obj.nonce) is True

    def test_no_expiration_passes_domain_check(self, settings):
        """Test that a message without expirationTime passes the expiration check
        (it will fail later at signature verification, but domain/expiration checks pass)"""
        settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost"]
        test_address = "0x742d35cC6634c0532925A3b844bc9E7595F0beB1"
        nonce_obj = Nonce.create_nonce(ttl=300)

        # Message without expirationTime - should pass domain + expiration checks
        # but fail at signature verification (we didn't sign it)
        payload = {
            "message": create_account_siwe_message(test_address, nonce_obj.nonce),
            "signature": "0x1234",
        }

        response = client.post(
            "/account/verify",
            json.dumps(payload),
            content_type="application/json",
        )

        # The nonce should be consumed (domain + expiration passed, nonce used, then sig fails)
        # Response should be 400 (signature verification failure), not nonce or domain error
        assert response.status_code == 400
        # Nonce was consumed because validation passed
        assert Nonce.use_nonce(nonce_obj.nonce) is False
