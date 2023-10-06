from unittest.mock import Mock, patch

import pytest
from account.models import AccountAPIKey
from registry.api import v1
from scorer.test.conftest import (
    scorer_account,
    scorer_api_key,
    scorer_community_with_binary_scorer,
    scorer_user,
)
from submit_passport import handler

# Sample mock event
sample_event = {
    "headers": {"x-api-key": "sample_key"},
    "body": '{"some_key": "some_value"}',
}

pytestmark = pytest.mark.django_db


def make_test_event(api_key, address, community_id):
    return {
        "requestContext": {
            "elb": {
                "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
            }
        },
        "httpMethod": "POST",
        "path": "/registry/submit-passport",
        "queryStringParameters": {},
        "headers": {
            "content-length": "73",
            "content-type": "application/json",
            "host": "api.staging.scorer.gitcoin.co",
            "user-agent": "k6/0.46.0 (https://k6.io/)",
            "x-amzn-trace-id": "Root=1-650373d8-19455f7f1bfd3c6f0fc3f323",
            "x-api-key": api_key,
            "x-forwarded-for": "164.90.200.92",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https",
        },
        "body": {"address": address, "community": community_id},
        "isBase64Encoded": False,
    }


def test_successful_authentication(
    scorer_api_key, scorer_account, scorer_community_with_binary_scorer
):
    event = make_test_event(
        scorer_api_key, scorer_account.address, scorer_community_with_binary_scorer.id
    )

    response = handler(event, None)
    assert response["statusCode"] == 200
