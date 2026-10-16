from django.contrib.auth.models import User
from django.test import Client, TestCase
from ninja_jwt.schema import RefreshToken


class ValidateTokenTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser-1", password="12345")
        self.client = Client()

    def _access_token(self, ip_address):
        # Mint a real token the same way /account/verify does, so the endpoint's
        # JWT validation runs for real rather than being mocked out.
        refresh = RefreshToken.for_user(self.user)
        refresh["ip_address"] = ip_address
        return refresh.access_token

    def _validate(self, token, remote_addr="127.0.0.1"):
        return self.client.post(
            "/account/validate_token",
            {"token": str(token)},
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        )

    def test_returns_exp_when_ip_matches(self):
        token = self._access_token("127.0.0.1")

        response = self._validate(token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["exp"], token["exp"])

    def test_rejects_token_when_ip_changed(self):
        token = self._access_token("10.0.0.1")

        response = self._validate(token, remote_addr="127.0.0.1")

        self.assertEqual(response.status_code, 401)

    def test_rejects_invalid_token(self):
        response = self._validate("not-a-jwt")

        self.assertEqual(response.status_code, 401)
