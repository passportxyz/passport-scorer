# content of conftest.py
import pytest
from django.conf import settings
from django.test import Client
from web3 import Web3

from account.models import Account, AccountAPIKey

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()


@pytest.fixture(
    params=[
        ("get", "/v2/stamps/SCORER/score/ADDRESS"),
        ("get", "/v2/stamps/ADDRESS"),
        ("get", "/v2/stamps/metadata"),
    ]
)
def api_path_that_requires_auth(request, scorer_community):
    method, path = request.param
    path = path.replace("SCORER", str(scorer_community.id)).replace(
        "ADDRESS", scorer_community.account.address
    )
    return (method, path)


def test_authentication_is_required_token(
    api_path_that_requires_auth, scorer_community
):
    """
    Test that bad api keys past in as tokens are rejected
    """
    method, path = api_path_that_requires_auth
    client = Client()

    method_fn = client.get
    if method == "post":
        method_fn = client.post

    response = method_fn(
        path,
        HTTP_AUTHORIZATION="Token " + "some bad API_KEY",
    )
    assert response.status_code == 401


def test_authentication_works_with_token(
    api_path_that_requires_auth, scorer_user, scorer_community
):
    """
    Test that API key is accepted if it is valid token and present in the HTTP_AUTHORIZATION header
    """
    method, path = api_path_that_requires_auth
    client = Client()

    account = scorer_community.account

    (_, secret) = AccountAPIKey.objects.create_key(
        account=account, name="Token for user 1"
    )

    method_fn = client.get
    if method == "post":
        method_fn = client.post

    response = method_fn(
        path,
        HTTP_AUTHORIZATION="Token " + secret,
    )
    # We should not get back any unauuthorized or forbidden errors
    assert response.status_code != 401
    assert response.status_code != 403


def test_authentication_is_required_api_key(api_path_that_requires_auth):
    """
    Test that bad api keys are rejected
    """
    method, path = api_path_that_requires_auth
    client = Client()

    method_fn = client.get
    if method == "post":
        method_fn = client.post

    response = method_fn(
        path,
        **{"HTTP_X-API-Key": "some bad API_KEY"},
    )
    assert response.status_code == 401


def test_authentication_works_with_api_key(
    api_path_that_requires_auth, scorer_user, scorer_community
):
    """
    Test that API key is accepted if it is valid and present in HTTP_X-API-Key header"""
    method, path = api_path_that_requires_auth
    client = Client()

    account = scorer_community.account

    (_, secret) = AccountAPIKey.objects.create_key(
        account=account, name="Token for user 1"
    )

    method_fn = client.get
    if method == "post":
        method_fn = client.post

    response = method_fn(
        path,
        **{"HTTP_X-API-Key": secret},
    )
    # We should not get back any unauuthorized or forbidden errors
    assert response.status_code != 401
    assert response.status_code != 403
