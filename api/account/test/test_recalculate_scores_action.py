from unittest.mock import MagicMock

import pytest

from account.admin import recalculate_scores
from account.models import Community

pytestmark = pytest.mark.django_db


def test_starts_cloud_run_job_when_configured(settings, mocker, scorer_community):
    settings.RESCORE_CLOUD_RUN_JOB = "projects/p/locations/l/jobs/rescore"
    settings.RESCORE_QUEUE_URL = "https://sqs.example/queue"
    run_job = mocker.patch("account.admin.run_job", return_value="operations/1")
    boto3_client = mocker.patch("account.admin.boto3.client")
    modeladmin = MagicMock()

    recalculate_scores(
        modeladmin, MagicMock(), Community.objects.filter(id=scorer_community.id)
    )

    run_job.assert_called_once_with(
        "projects/p/locations/l/jobs/rescore",
        ["--community-ids", str(scorer_community.id)],
    )
    boto3_client.assert_not_called()
    assert "operations/1" in modeladmin.message_user.call_args[0][1]


def test_sends_to_sqs_when_no_job_is_configured(settings, mocker, scorer_community):
    settings.RESCORE_CLOUD_RUN_JOB = ""
    settings.RESCORE_QUEUE_URL = "https://sqs.example/queue"
    run_job = mocker.patch("account.admin.run_job")
    sqs = mocker.patch("account.admin.boto3.client").return_value
    sqs.send_message.return_value = {"MessageId": "m-1"}

    recalculate_scores(
        MagicMock(), MagicMock(), Community.objects.filter(id=scorer_community.id)
    )

    run_job.assert_not_called()
    assert sqs.send_message.call_args.kwargs["QueueUrl"] == "https://sqs.example/queue"
    assert sqs.send_message.call_args.kwargs["MessageBody"] == str(scorer_community.id)
