# content of conftest.py
import pytest
from account.models import Account, AccountAPIKey
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from web3 import Web3

pytestmark = pytest.mark.django_db

User = get_user_model()
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC


@pytest.fixture(
    params=[
        ("get", "/analytics/score/"),
        ("get", "/analytics/score/1"),
    ]
)
def api_path_that_requires_auth(request):
    return request.param


def test_analytics_access_denied_without_researcher_permissions(
    api_path_that_requires_auth, scorer_user
):
    """
    Test that a user without researcher permissions but a valid api key is denied access to the analytics API
    """
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    account = Account.objects.create(user=scorer_user, address=web3_account.address)

    (_, secret) = AccountAPIKey.objects.create_key(
        account=account, name="Token for user 1"
    )

    _, path = api_path_that_requires_auth
    client = Client()

    method_fn = client.get

    response = method_fn(
        path,
        **{"HTTP_X-API-Key": secret},
    )

    response_data = response.json()
    assert response.status_code == 403
    assert response_data["detail"] == "You are not allowed to access this endpoint."


def test_analytics_with_researcher_permissions_bad_apikey(
    api_path_that_requires_auth,
    scorer_account,
):
    """
    Test that a user without a valid api key but with researcher permissions is denied access to the analytics API
    """

    group, _ = Group.objects.get_or_create(name="Researcher")

    scorer_account.user.groups.add(group)

    _, path = api_path_that_requires_auth
    client = Client()

    method_fn = client.get

    response = method_fn(
        path,
        **{"HTTP_X-API-Key": "bad_api_key"},
    )

    response_data = response.json()
    assert response.status_code == 401
    assert response_data["detail"] == "Invalid API Key."


def test_analytics_with_researcher_permissions_and_apikey(
    api_path_that_requires_auth, scorer_api_key, scorer_account, scorer_community
):
    """
    Test that a user with a valid api key and with researcher permissions is allowed access to the analytics API
    """

    group, _ = Group.objects.get_or_create(name="Researcher")

    scorer_account.user.groups.add(group)

    _, path = api_path_that_requires_auth

    client = Client()

    method_fn = client.get

    response = method_fn(
        path,
        **{"HTTP_X-API-Key": scorer_api_key},
    )

    assert response.status_code == 200


def test_authentication_is_required_token(api_path_that_requires_auth):
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


def test_authentication_works_with_api_key(api_path_that_requires_auth, scorer_user):
    """
    Test that API key is accepted if it is valid and present in HTTP_X-API-Key header"""
    method, path = api_path_that_requires_auth
    client = Client()

    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    account = Account.objects.create(user=scorer_user, address=web3_account.address)

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
    assert response.status_code != 401
