# content of conftest.py
import json

import pytest
from django.conf import settings
from django.test import Client
from web3 import Web3

from account.models import AccountAPIKey, AccountAPIKeyAnalytics

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC


@pytest.fixture(
    params=[
        ("get", "/registry/signing-message"),
        ("post", "/registry/submit-passport"),
        ("get", "/registry/score/3"),
        ("get", "/registry/score/3/0x0"),
    ]
)
def api_path_that_requires_api_tracing(request):
    return request.param


def test_authentication_works_with_token(
    api_path_that_requires_api_tracing, scorer_user, scorer_community
):
    """
    Test that API key is accepted if it is valid token and present in the HTTP_AUTHORIZATION header
    """
    method, path = api_path_that_requires_api_tracing
    client = Client()

    account = scorer_community.account

    (_, secret) = AccountAPIKey.objects.create_key(
        account=account, name="Token for user 1"
    )

    if method == "post":
        # Now we submit a duplicate hash, and expect deduplication to happen
        submission_test_payload = {
            "community": scorer_community.id,
            "address": account.address,
        }

        response = client.post(
            path,
            json.dumps(submission_test_payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Token " + secret,
        )

    else:
        response = client.get(
            path,
            HTTP_AUTHORIZATION="Token " + secret,
        )
    # We should not get back any unauuthorized or forbidden errors
    assert response.status_code != 401
    assert response.status_code != 403

    key_analytics = AccountAPIKeyAnalytics.objects.order_by("-created_at")[0]
    assert key_analytics.path == path
    assert key_analytics.path_segments == path.split("/")[1:]
