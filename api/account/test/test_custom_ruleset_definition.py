import pytest
from django.conf import settings
from django.test import Client

from account.models import CustomCredentialRuleset

pytestmark = pytest.mark.django_db

DEFINITION = {
    "name": "PlanTestNFT",
    "condition": {
        "contracts": [
            {
                "address": "0x0000000000000000000000000000000000000000",
                "chainId": 1,
                "standard": "ERC-721",
            }
        ]
    },
}


@pytest.fixture
def ruleset():
    # provider_id is computed by CustomCredentialRuleset.save(); do not set it.
    return CustomCredentialRuleset.objects.create(
        credential_type=CustomCredentialRuleset.CredentialType.NFTHolder,
        definition=DEFINITION,
    )


def _encoded(provider_id):
    return provider_id.replace("#", "%23")


def test_public_route_returns_definition(ruleset):
    response = Client().get(
        f"/account/customization/credential/{_encoded(ruleset.provider_id)}"
    )

    assert response.status_code == 200
    assert response.json()["ruleset"] == DEFINITION


def test_public_route_404s_for_unknown_provider():
    response = Client().get(
        "/account/customization/credential/NFTHolder%23Unknown%2300000000"
    )

    assert response.status_code == 404


def test_internal_route_returns_definition(ruleset):
    response = Client().get(
        f"/internal/customization/credential/{_encoded(ruleset.provider_id)}",
        HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
    )

    assert response.status_code == 200
    assert response.json()["ruleset"] == DEFINITION


def test_internal_route_requires_auth(ruleset):
    response = Client().get(
        f"/internal/customization/credential/{_encoded(ruleset.provider_id)}"
    )

    assert response.status_code == 401


def test_internal_route_rejects_wrong_token(ruleset):
    response = Client().get(
        f"/internal/customization/credential/{_encoded(ruleset.provider_id)}",
        HTTP_AUTHORIZATION="not-the-internal-token",
    )

    assert response.status_code == 401
