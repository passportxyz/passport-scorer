from datetime import datetime, timedelta, timezone

import pytest

from account.siwe_validation import validate_siwe_domain, validate_siwe_expiration


class TestValidateSiweDomain:
    def test_valid_domain(self):
        assert validate_siwe_domain("app.passport.xyz", ["app.passport.xyz"]) is True

    def test_invalid_domain(self):
        assert validate_siwe_domain("evil.com", ["app.passport.xyz"]) is False

    def test_none_domain(self):
        assert validate_siwe_domain(None, ["app.passport.xyz"]) is False

    def test_empty_string_domain(self):
        assert validate_siwe_domain("", ["app.passport.xyz"]) is False

    def test_case_insensitive(self):
        assert validate_siwe_domain("APP.PASSPORT.XYZ", ["app.passport.xyz"]) is True

    def test_empty_allowlist(self):
        assert validate_siwe_domain("app.passport.xyz", []) is False

    def test_multiple_allowed_domains(self):
        allowed = ["app.passport.xyz", "developer.passport.xyz"]
        assert validate_siwe_domain("developer.passport.xyz", allowed) is True

    def test_localhost_with_port(self):
        assert validate_siwe_domain("localhost:3000", ["localhost:3000"]) is True


class TestValidateSiweExpiration:
    def test_no_expiration_returns_true(self):
        assert validate_siwe_expiration(None) is True

    def test_future_expiration_returns_true(self):
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        assert validate_siwe_expiration(future) is True

    def test_past_expiration_returns_false(self):
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        assert validate_siwe_expiration(past) is False

    def test_malformed_expiration_returns_false(self):
        assert validate_siwe_expiration("not-a-date") is False

    def test_z_suffix_handled(self):
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert validate_siwe_expiration(future.strftime("%Y-%m-%dT%H:%M:%SZ")) is True

    def test_empty_string_returns_false(self):
        assert validate_siwe_expiration("") is False

    def test_naive_datetime_without_timezone_returns_false(self):
        assert validate_siwe_expiration("2099-12-31T23:59:59") is False
