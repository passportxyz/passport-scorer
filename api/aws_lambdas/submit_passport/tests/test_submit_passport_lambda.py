import base64
import json
from copy import deepcopy

import pytest

from account.models import AccountAPIKeyAnalytics
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from aws_lambdas.scorer_api_passport.utils import strip_event
from registry.test.test_passport_submission import mock_passport

from ..submit_passport import _handler

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


def make_test_event_with_base64_encoded_body(api_key, address, community_id):
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
        "body": base64.b64encode(
            json.dumps({"address": address, "community": community_id}).encode("utf-8")
        ),
        "isBase64Encoded": True,
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

    mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    address = passport_holder_addresses[0]["address"].lower()
    event = make_test_event(
        scorer_api_key, address, scorer_community_with_binary_scorer.id
    )

    response = _handler(event, MockContext())

    assert response is not None
    body = json.loads(response["body"])

    assert body["address"] == address
    assert body["score"] == "0"
    assert body["status"] == "DONE"

    assert body["evidence"] == {
        "type": "ThresholdScoreCheck",
        "success": False,
        "rawScore": 0.9329999999999999,
        "threshold": 20.0,
    }
    assert body["error"] is None
    assert body["stamp_scores"] == {"Ens": 0.408, "Google": 0.525}
    # We just check that something != None was recorded for the last timestamp
    assert body["last_score_timestamp"] is not None

    assert response["statusCode"] == 200


def test_successful_authentication_and_base64_encoded_body(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):
    """
    Tests that authentication is successful given correct credentials.
    Also this test uses a body payload that is base64 encoded.
    """

    mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    address = passport_holder_addresses[0]["address"].lower()
    event = make_test_event_with_base64_encoded_body(
        scorer_api_key, address, scorer_community_with_binary_scorer.id
    )

    response = _handler(event, MockContext())

    assert response is not None
    body = json.loads(response["body"])

    assert body["address"] == address
    assert body["score"] == "0"
    assert body["status"] == "DONE"
    assert body["evidence"] == {
        "type": "ThresholdScoreCheck",
        "success": False,
        "rawScore": 0.9329999999999999,
        "threshold": 20.0,
    }
    assert body["error"] is None
    assert body["stamp_scores"] == {"Ens": 0.408, "Google": 0.525}
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

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 401


def test_strip_event():
    stripped_data, event = strip_event(sample_event)


def test_strip_event_strips_the_api_key(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
):
    """
    Tests that authentication is successful given correct credentials.
    """

    address = passport_holder_addresses[0]["address"].lower()
    event = make_test_event(
        scorer_api_key, address, scorer_community_with_binary_scorer.id
    )
    initial_event = deepcopy(event)
    sensitive_data, event = strip_event(event)

    assert sensitive_data["x-api-key"] == initial_event["headers"]["x-api-key"]
    assert event["headers"]["x-api-key"] == "***"

    # Events hould equal the initial event after adding back the stripped data
    event["headers"]["x-api-key"] = sensitive_data["x-api-key"]
    assert event == initial_event


def test_strip_event_handle_missing_api_key(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
):
    """
    Tests that authentication is successful given correct credentials.
    """

    address = passport_holder_addresses[0]["address"].lower()
    event = make_test_event(
        scorer_api_key, address, scorer_community_with_binary_scorer.id
    )

    # Delete the "x-api-key" we want to assume our event does not have it at the beginning
    del event["headers"]["x-api-key"]
    assert "x-api-key" not in event["headers"]

    initial_event = deepcopy(event)

    sensitive_data, event = strip_event(event)

    assert len(sensitive_data) == 0
    assert event == initial_event


def test_successful_authentication_and_analytics_logging(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):
    """
    Tests that proper analytics entry is registered in the DB
    """

    mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    address = passport_holder_addresses[0]["address"].lower()
    event = {
        "requestContext": {
            "elb": {
                "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
            }
        },
        "httpMethod": "POST",
        "path": "/registry/submit-passport",
        "queryStringParameters": {"a": "b"},
        "headers": {
            "content-length": "73",
            "content-type": "application/json",
            "host": "api.staging.scorer.gitcoin.co",
            "user-agent": "k6/0.46.0 (https://k6.io/)",
            "x-amzn-trace-id": "Root=1-650373d8-19455f7f1bfd3c6f0fc3f323",
            "x-api-key": scorer_api_key,
            "x-forwarded-for": "164.90.200.92",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https",
        },
        "body": json.dumps(
            {
                "address": address,
                "community": scorer_community_with_binary_scorer.id,
            }
        ),
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 200

    # Check for the proper analytics entry
    analytics_entry = AccountAPIKeyAnalytics.objects.order_by("-created_at")[0]
    assert analytics_entry.path == event["path"]
    assert analytics_entry.path_segments == ["registry", "submit-passport"]
    assert analytics_entry.payload == {
        "address": address,
        "community": scorer_community_with_binary_scorer.id,
    }
    assert analytics_entry.query_params == {"a": "b"}
    assert analytics_entry.headers == {  # header without api key
        "content-length": "73",
        "content-type": "application/json",
        "host": "api.staging.scorer.gitcoin.co",
        "user-agent": "k6/0.46.0 (https://k6.io/)",
        "x-amzn-trace-id": "Root=1-650373d8-19455f7f1bfd3c6f0fc3f323",
        "x-forwarded-for": "164.90.200.92",
        "x-forwarded-port": "443",
        "x-forwarded-proto": "https",
        "x-api-key": "***",
    }

    assert analytics_entry.error is None


def test_failed_authentication_and_analytics_logging(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):
    """
    Tests that proper analytics entry is registered in the DB
    """

    mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    address = passport_holder_addresses[0]["address"].lower()
    event = {
        "requestContext": {
            "elb": {
                "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
            }
        },
        "httpMethod": "POST",
        "path": "/registry/submit-passport",
        "queryStringParameters": {"a": "b"},
        "headers": {
            "content-length": "73",
            "content-type": "application/json",
            "host": "api.staging.scorer.gitcoin.co",
            "user-agent": "k6/0.46.0 (https://k6.io/)",
            "x-amzn-trace-id": "Root=1-650373d8-19455f7f1bfd3c6f0fc3f323",
            "x-api-key": scorer_api_key + "-BAD",
            "x-forwarded-for": "164.90.200.92",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https",
        },
        "body": json.dumps(
            {
                "address": address,
                "community": scorer_community_with_binary_scorer.id,
            }
        ),
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 401

    # Check for the proper analytics entry
    analytics_entry_count = AccountAPIKeyAnalytics.objects.order_by(
        "-created_at"
    ).count()

    # because of the bad API key with expect no logs
    assert analytics_entry_count == 0


def test_bad_scorer_id_and_analytics_logging(
    scorer_api_key,
    scorer_community_with_binary_scorer,
    passport_holder_addresses,
    mocker,
):
    """
    Tests that proper analytics entry is registered in the DB
    """

    mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    )
    mocker.patch("registry.atasks.validate_credential", side_effect=[[], [], []])
    address = passport_holder_addresses[0]["address"].lower()
    event = {
        "requestContext": {
            "elb": {
                "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
            }
        },
        "httpMethod": "POST",
        "path": "/registry/submit-passport",
        "queryStringParameters": {"a": "b"},
        "headers": {
            "content-length": "73",
            "content-type": "application/json",
            "host": "api.staging.scorer.gitcoin.co",
            "user-agent": "k6/0.46.0 (https://k6.io/)",
            "x-amzn-trace-id": "Root=1-650373d8-19455f7f1bfd3c6f0fc3f323",
            "x-api-key": scorer_api_key,
            "x-forwarded-for": "164.90.200.92",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https",
        },
        "body": json.dumps(
            {
                "address": address,
                "community": 123123,
            }
        ),
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 404
    # Check for the proper analytics entry
    analytics_entry = AccountAPIKeyAnalytics.objects.order_by("-created_at")[0]
    assert analytics_entry.path == event["path"]
    assert analytics_entry.path_segments == ["registry", "submit-passport"]
    assert analytics_entry.payload == {
        "address": address,
        "community": 123123,
    }
    assert analytics_entry.query_params == {"a": "b"}
    assert analytics_entry.headers == {  # header without api key
        "content-length": "73",
        "content-type": "application/json",
        "host": "api.staging.scorer.gitcoin.co",
        "user-agent": "k6/0.46.0 (https://k6.io/)",
        "x-amzn-trace-id": "Root=1-650373d8-19455f7f1bfd3c6f0fc3f323",
        "x-forwarded-for": "164.90.200.92",
        "x-forwarded-port": "443",
        "x-forwarded-proto": "https",
        "x-api-key": "***",
    }

    assert analytics_entry.error == "No scorer matches the given criteria."


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
