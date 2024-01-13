import json

import pytest
from account.models import Community
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext

from ..rescore import handler

pytestmark = pytest.mark.django_db


def make_test_event(community_ids):
    return {
        "Records": [
            {
                "messageId": "d920e69f-3815-4910-95a2-9acd73ffff31",
                "receiptHandle": "abc",
                "body": ",".join([str(id) for id in community_ids]),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1704486843732",
                    "SenderId": "594035263039",
                    "ApproximateFirstReceiveTimestamp": "1704486843742",
                },
                "messageAttributes": {
                    "type": {
                        "stringValue": "rescore",
                        "stringListValues": [],
                        "binaryListValues": [],
                        "dataType": "String",
                    }
                },
                "md5OfBody": "d97350c83038f254a53896553c245bd3",
                "md5OfMessageAttributes": "ef43aa1d5a646b677f90a87e93fe480b",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:region:account:queue",
                "awsRegion": "region",
            }
        ]
    }


def test_successful_processing(
    scorer_community,
    scorer_community_with_binary_scorer,
    mocker,
):
    """
    Tests that an SQS message is processed successfully
    """

    recalc_mock = mocker.patch("aws_lambdas.rescore.recalculate_scores")

    community_ids = [scorer_community.id, scorer_community_with_binary_scorer.id]

    test_event = make_test_event(
        community_ids,
    )
    response = handler(test_event, MockContext())

    assert response is not None
    body = json.loads(response["body"])

    assert body["status"] == "success"

    assert recalc_mock.call_count == 1
    assert recalc_mock.call_args_list[0][0][0].count() == len(community_ids)
    assert recalc_mock.call_args_list[0][0][0][0].id in community_ids
    assert recalc_mock.call_args_list[0][0][0][1].id in community_ids
