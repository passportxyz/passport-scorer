import base64
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from account.models import AccountAPIKeyAnalytics
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from aws_lambdas.scorer_api_passport.utils import strip_event
from ceramic_cache.models import CeramicCache
from registry.test.test_passport_submission import mock_passport
from scorer.config.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from v2.test.test_api_dedup import avalidate_credentials_side_effect, wallet_a, wallet_b

from ..stamp_score_GET import _handler

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
        "path": f"/v2/stamps/{community_id}/score/{address}",
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
        "path": f"/v2/stamps/{community_id}/score/{address}",
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

            # pylint: disable=no-value-for-parameter
            response = _handler(event, MockContext())

            assert response is not None
            body = json.loads(response["body"])

            assert body["address"] == address
            assert body["score"] == "0.93300"
            assert body["passing_score"] == False
            assert body["threshold"] == "20.00000"

            assert body["error"] is None
            assert body["stamps"] == {
                "Ens": {
                    "score": "0.40800",
                    "dedup": False,
                    "expiration_date": next(
                        (
                            datetime.fromisoformat(
                                stamp["credential"]["expirationDate"]
                            ).isoformat()
                            for stamp in mock_passport["stamps"]
                            if stamp["provider"] == "Ens"
                        ),
                        None,
                    ),
                },
                "Google": {
                    "score": "0.52500",
                    "dedup": False,
                    "expiration_date": next(
                        (
                            datetime.fromisoformat(
                                stamp["credential"]["expirationDate"]
                            ).isoformat()
                            for stamp in mock_passport["stamps"]
                            if stamp["provider"] == "Google"
                        ),
                        None,
                    ),
                },
            }
            # We just check that something != None was recorded for the last timestamp
            assert body["expiration_timestamp"] is not None

            assert response["statusCode"] == 200


@patch(
    "registry.atasks.avalidate_credentials",
    side_effect=avalidate_credentials_side_effect,
)
def test_successful_authentication_and_dedup_flag(
    validate_credential,
    weight_config,
    scorer_community,
    scorer_api_key,
    # mocker,
):
    """
    Test the following flow:
    - wallet A has a valid stamp & checks that the get score returs the proper stamp
    - wallet B claims the same stamp (same hash => it is deduped) the get score for wallet B returns the score is 0 & the dedup flag is set to True
    - wallet A checks the score again, there are no changes in the returned stamps.
    """

    now = datetime.now(timezone.utc)
    days_ago = (now - timedelta(days=2)).isoformat()
    days_later = (now + timedelta(days=2)).isoformat()

    sample_provider = "LinkedinV2"
    sample_provider_hash = "v0.0.0:Ft7mqRdvJ9jNgSSowb9qdcMeOzswOeighIOvk0wn964="

    sample_stamp = CeramicCache.objects.create(
        address=wallet_a,
        provider=sample_provider,
        stamp={
            "type": ["VerifiableCredential"],
            "proof": {
                "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..34uD8jKn2N_yE8pY4ErzVD8pJruZq7qJaCxx8y0SReY2liZJatfeQUv1nqmZH19a-svOyfHt_VbmKvh6A5vwBw",
                "type": "Ed25519Signature2018",
                "created": days_ago,
                "proofPurpose": "assertionMethod",
                "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
            },
            "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "issuanceDate": days_ago,
            "expirationDate": days_later,
            "credentialSubject": {
                "id": f"did:pkh:eip155:1:{wallet_a}",
                "hash": sample_provider_hash,
                "@context": [
                    {
                        "hash": "https://schema.org/Text",
                        "provider": sample_provider,
                    }
                ],
                "provider": sample_provider,
            },
        },
    )

    event_wallet_a = make_test_event(scorer_api_key, wallet_a, scorer_community.id)
    # pylint: disable=no-value-for-parameter
    response_wallet_a = _handler(event_wallet_a, MockContext())

    assert response_wallet_a is not None
    assert response_wallet_a["statusCode"] == 200
    body_wallet_a = json.loads(response_wallet_a["body"])
    assert body_wallet_a["address"] == wallet_a.lower()
    assert (
        body_wallet_a["score"]
        == f"{Decimal(GITCOIN_PASSPORT_WEIGHTS[sample_provider]):.5f}"
    )
    assert body_wallet_a["passing_score"] == False
    assert body_wallet_a["threshold"] == "20.00000"

    assert body_wallet_a["error"] is None
    assert body_wallet_a["expiration_timestamp"] == days_later
    assert body_wallet_a["stamps"] == {
        sample_provider: {
            "score": f"{Decimal(GITCOIN_PASSPORT_WEIGHTS[sample_provider]):.5f}",
            "dedup": False,
            "expiration_date": days_later,
        }
    }

    dedup_stamp = CeramicCache.objects.create(
        address=wallet_b,
        provider=sample_provider,
        stamp={
            "type": ["VerifiableCredential"],
            "proof": {
                "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..34uD8jKn2N_yE8pY4ErzVD8pJruZq7qJaCxx8y0SReY2liZJatfeQUv1nqmZH19a-svOyfHt_VbmKvh6A5vwBw",
                "type": "Ed25519Signature2018",
                "created": days_ago,
                "proofPurpose": "assertionMethod",
                "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
            },
            "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "issuanceDate": days_ago,
            "expirationDate": days_later,
            "credentialSubject": {
                "id": f"did:pkh:eip155:1:{wallet_b}",
                "hash": sample_provider_hash,
                "@context": [
                    {
                        "hash": "https://schema.org/Text",
                        "provider": sample_provider,
                    }
                ],
                "provider": sample_provider,
            },
        },
    )

    event_wallet_b = make_test_event(scorer_api_key, wallet_b, scorer_community.id)
    # pylint: disable=no-value-for-parameter
    response_wallet_b = _handler(event_wallet_b, MockContext())

    assert response_wallet_b is not None
    assert response_wallet_b["statusCode"] == 200
    body_wallet_b = json.loads(response_wallet_b["body"])
    assert body_wallet_b["address"] == wallet_b.lower()
    assert body_wallet_b["score"] == "0.00000"
    assert body_wallet_b["passing_score"] == False
    assert body_wallet_b["threshold"] == "20.00000"

    assert body_wallet_b["error"] is None
    assert body_wallet_b["expiration_timestamp"] is None
    assert body_wallet_b["stamps"] == {
        sample_provider: {
            "score": "0.00000",
            "dedup": True,
            "expiration_date": days_later,
        }
    }

    event_wallet_a_back = make_test_event(scorer_api_key, wallet_a, scorer_community.id)
    response_wallet_a_back = _handler(event_wallet_a_back, MockContext())
    assert response_wallet_a_back is not None
    assert response_wallet_a_back["statusCode"] == 200
    body_wallet_a_back = json.loads(response_wallet_a_back["body"])
    assert body_wallet_a_back["address"] == wallet_a.lower()
    assert (
        body_wallet_a_back["score"]
        == f"{Decimal(GITCOIN_PASSPORT_WEIGHTS[sample_provider]):.5f}"
    )
    assert body_wallet_a_back["passing_score"] == False
    assert body_wallet_a_back["threshold"] == "20.00000"

    assert body_wallet_a_back["error"] is None
    assert body_wallet_a_back["expiration_timestamp"] == days_later
    assert body_wallet_a_back["stamps"] == {
        sample_provider: {
            "score": f"{Decimal(GITCOIN_PASSPORT_WEIGHTS[sample_provider]):.5f}",
            "dedup": False,
            "expiration_date": days_later,
        }
    }


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

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):
            address = passport_holder_addresses[0]["address"].lower()
            event = make_test_event_with_base64_encoded_body(
                scorer_api_key, address, scorer_community_with_binary_scorer.id
            )

            # pylint: disable=no-value-for-parameter
            response = _handler(event, MockContext())

            assert response is not None
            body = json.loads(response["body"])

            assert body["address"] == address
            assert body["score"] == "0.93300"
            assert body["passing_score"] == False
            assert body["threshold"] == "20.00000"
            assert body["error"] is None
            assert body["stamps"] == {
                "Ens": {
                    "score": "0.40800",
                    "dedup": False,
                    "expiration_date": next(
                        (
                            datetime.fromisoformat(
                                stamp["credential"]["expirationDate"]
                            ).isoformat()
                            for stamp in mock_passport["stamps"]
                            if stamp["provider"] == "Ens"
                        ),
                        None,
                    ),
                },
                "Google": {
                    "score": "0.52500",
                    "dedup": False,
                    "expiration_date": next(
                        (
                            datetime.fromisoformat(
                                stamp["credential"]["expirationDate"]
                            ).isoformat()
                            for stamp in mock_passport["stamps"]
                            if stamp["provider"] == "Google"
                        ),
                        None,
                    ),
                },
            }
            # We just check that something != None was recorded for the last timestamp
            assert body["expiration_timestamp"] is not None

            assert response["statusCode"] == 200


def test_unsucessfull_auth(scorer_account, scorer_community_with_binary_scorer):
    """
    Tests that authentication fails given incorrect credentials.
    """
    event = make_test_event(
        "bad_key", scorer_account.address, scorer_community_with_binary_scorer.id
    )

    # pylint: disable=no-value-for-parameter
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

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):
            address = passport_holder_addresses[0]["address"].lower()
            event = {
                "requestContext": {
                    "elb": {
                        "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
                    }
                },
                "httpMethod": "POST",
                "path": f"/v2/stamps/{scorer_community_with_binary_scorer.id}/score/{address}",
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

            # pylint: disable=no-value-for-parameter
            response = _handler(event, MockContext())

            assert response is not None
            assert response["statusCode"] == 200

            # Check for the proper analytics entry
            analytics_entry = AccountAPIKeyAnalytics.objects.order_by("-created_at")[0]
            assert analytics_entry.path == event["path"]
            # double check this is correct
            assert analytics_entry.path_segments == [
                "v2",
                "stamps",
                str(scorer_community_with_binary_scorer.id),
                "score",
                "0x6077ebc94bb5a4ac9a54f2e47d29b3ed580e5b8b",
            ]
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

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):
            address = passport_holder_addresses[0]["address"].lower()
            event = {
                "requestContext": {
                    "elb": {
                        "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
                    }
                },
                "httpMethod": "POST",
                "path": f"/v2/stamps/{scorer_community_with_binary_scorer.id}/score/{address}",
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

            # pylint: disable=no-value-for-parameter
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
    passport_holder_addresses,
    mocker,
):
    """
    Tests that proper analytics entry is registered in the DB
    """

    with mocker.patch(
        "registry.atasks.aget_passport",
        return_value=mock_passport,
    ):
        with mocker.patch(
            "registry.atasks.validate_credential", side_effect=[[], [], []]
        ):
            address = passport_holder_addresses[0]["address"].lower()
            event = {
                "requestContext": {
                    "elb": {
                        "targetGroupArn": "arn:aws:elasticloadbalancing:us-west-2:515520736917:targetgroup/testTargetGroup-e050da0/c8f86571a77b9bc5"
                    }
                },
                "httpMethod": "POST",
                "path": f"/v2/stamps/{123123}/score/{address}",
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

            # pylint: disable=no-value-for-parameter
            response = _handler(event, MockContext())

            assert response is not None
            assert response["statusCode"] == 404
            # Check for the proper analytics entry
            analytics_entry = AccountAPIKeyAnalytics.objects.order_by("-created_at")[0]
            assert analytics_entry.path == event["path"]
            assert analytics_entry.path_segments == [
                "v2",
                "stamps",
                "123123",
                "score",
                "0x6077ebc94bb5a4ac9a54f2e47d29b3ed580e5b8b",
            ]
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
