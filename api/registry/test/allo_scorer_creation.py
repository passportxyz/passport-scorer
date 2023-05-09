import json

import pytest
from account.models import AccountAPIKey, APIKeyPermissions, Community
from django.test import Client
from django.urls import reverse

client = Client()

pytestmark = pytest.mark.django_db


def test_create_allo_scorer_success(scorer_account):
    permissions = APIKeyPermissions.objects.create(
        submit_passports=True, read_scores=True, create_scorers=True
    )
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Test API key", permissions=permissions
    )

    payload = {"name": "Test Community", "allo_scorer_id": "0x0000"}

    response = client.post(
        "/registry/allo/communities",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {secret}",
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["ok"] == True
    assert "scorer_id" in response_data
    assert "allo_scorer_id" in response_data

    # Verify the community was created in the database
    community = Community.objects.get(pk=response_data["scorer_id"])
    assert community.name == payload["name"]
    assert community.account == scorer_account
