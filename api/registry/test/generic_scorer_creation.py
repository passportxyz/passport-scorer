import json

import pytest
from account.models import AccountAPIKey, Community, Rules
from django.test import Client
from django.urls import reverse

client = Client()

pytestmark = pytest.mark.django_db


def test_create_generic_scorer_success(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account,
        name="Test API key",
    )

    payload = {"name": "Test Community", "external_scorer_id": "0x0000"}

    response = client.post(
        "/registry/scorer/generic",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {secret}",
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["ok"] == True
    assert "scorer_id" in response_data
    assert "external_scorer_id" in response_data

    # Verify the community was created in the database
    community = Community.objects.get(pk=response_data["scorer_id"])
    assert community.name == payload["name"]
    assert community.account == scorer_account


def test_create_generic_scorer_no_permission(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Test API key"
    )

    payload = {"name": "Test Community", "external_scorer_id": "0x0000"}

    response = client.post(
        "/registry/scorer/generic",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {secret}",
    )

    assert response.status_code == 403


def test_create_generic_scorer_too_many_communities(scorer_account, settings):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account,
        name="Test API key",
    )

    settings.GENERIC_COMMUNITY_CREATION_LIMIT = 1

    Community.objects.create(
        account=scorer_account,
        name="Existing Community",
        description="Test",
        use_case="Sybil Protection",
        rule=Rules.LIFO,
    )

    payload = {"name": "Test Community", "external_scorer_id": "0x0000"}

    response = client.post(
        "/registry/scorer/generic",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {secret}",
    )
    assert response.status_code == 400


def test_create_generic_scorer_duplicate_name(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account,
        name="Test API key",
    )

    Community.objects.create(
        account=scorer_account,
        name="Test Community",
        description="Test",
        use_case="Sybil Protection",
        rule=Rules.LIFO,
    )

    payload = {"name": "Test Community", "external_scorer_id": "0x0000"}

    response = client.post(
        "/registry/scorer/generic",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {secret}",
    )

    assert response.status_code == 400


def test_create_generic_scorer_no_name(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account,
        name="Test API key",
    )

    payload = {"name": "", "external_scorer_id": "0x0000"}

    response = client.post(
        "/registry/scorer/generic",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {secret}",
    )

    assert response.status_code == 422
