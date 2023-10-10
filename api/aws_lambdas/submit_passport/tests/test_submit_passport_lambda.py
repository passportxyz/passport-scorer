import json

import pytest
from registry.test.test_passport_submission import mock_passport

from ..submit_passport import handler

# Sample mock event
sample_event = {
    "headers": {"x-api-key": "sample_key"},
    "body": '{"some_key": "some_value"}',
}

pytestmark = pytest.mark.django_db


def make_test_event(api_key, address, community_id):
    """
    Creates a mock event for testing purposes.
    """
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
        "body": json.dumps({"address": address, "community": community_id}),
        "isBase64Encoded": False,
    }


def test_successful_authentication(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):
    """
    Tests that authentication is successful given correct credentials.
    """

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):
            address = passport_holder_addresses[0]["address"].lower()
            event = make_test_event(
                scorer_api_key, address, scorer_community_with_binary_scorer.id
            )

            response = handler(event, None)

            assert response is not None
            body = json.loads(response["body"])

            assert body["address"] == address
            assert body["score"] == "0"
            assert body["status"] == "DONE"
            assert body["evidence"] == {
                "type": "ThresholdScoreCheck",
                "success": False,
                "rawScore": 2,
                "threshold": 75.0,
            }
            assert body["error"] is None
            assert body["stamp_scores"] == {"Ens": 1.0, "Google": 1.0}
            # We just check that something != None was recorded for the last timestamp
            assert body["last_score_timestamp"] is not None

            assert response["statusCode"] == 200


def test_unsucessfull_auth(scorer_account, scorer_community_with_binary_scorer):
    """
    Tests that authentication fails given incorrect credentials.
    """
    event = make_test_event(
        "bad_key", scorer_account.address, scorer_community_with_binary_scorer.id
    )

    response = handler(event, None)

    assert response is not None
    assert response["statusCode"] == 403


# Conflicting with other rate limiting tests
# @override_settings(RATELIMIT_ENABLE=True)
# def test_rate_limiting(
#     scorer_api_key, scorer_account, scorer_community_with_binary_scorer
# ):
#     """
#     Tests that rate limiting works as expected.
#     """
#     (_, secret) = AccountAPIKey.objects.create_key(
#         account=scorer_account,
#         name="Token for user 1",
#         rate_limit="3/30seconds",
#     )
#     event = make_test_event(
#         secret, scorer_account.address, scorer_community_with_binary_scorer.id
#     )

#     for _ in range(3):
#         response = handler(event, None)
#         assert response is not None
#         assert response["statusCode"] == 200

#     rate_limit = handler(event, None)
#     assert rate_limit is not None
#     assert rate_limit["statusCode"] == 429
