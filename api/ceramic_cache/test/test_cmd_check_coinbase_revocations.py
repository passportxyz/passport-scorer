from datetime import UTC, datetime
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from freezegun import freeze_time

from ceramic_cache.models import CeramicCache, Revocation
from passport_admin.models import LastScheduledRun


@pytest.fixture
def mock_requests_post():
    with patch("requests.post") as mock_post:
        yield mock_post


@pytest.fixture
def mock_stdout():
    return StringIO()


@pytest.mark.django_db
class TestCheckCoinbaseRevocationsCommand:
    @freeze_time("2024-08-01 12:00:00")
    def test_first_run(self, mock_requests_post, mock_stdout):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "attestations": [
                    {"recipient": "0x123456789abcdef"},
                    {"recipient": "0xfedcba987654321"},
                ]
            }
        }
        mock_requests_post.return_value = mock_response

        CeramicCache.objects.create(
            address="0x123456789abcdef",
            provider="CoinbaseDualVerification",
            proof_value="proof1",
        )

        call_command("check_coinbase_revocations", stdout=mock_stdout)

        last_run = LastScheduledRun.objects.get(name="check_coinbase_revocations")
        assert last_run.last_run == datetime(2024, 8, 1, 12, 0, 0, tzinfo=UTC)

        output = mock_stdout.getvalue()
        assert (
            "Checking for revoked attestations between [1970-01-01 00:00:00+00:00, 2024-08-01 12:00:00+00:00)"
            in output
        )
        assert "Found 2 revoked addresses" in output
        assert (
            "Revoking stamp with proof_value=proof1 for address=0x123456789abcdef"
            in output
        )

    @freeze_time("2024-08-01 13:00:00")
    def test_subsequent_run(self, mock_requests_post, mock_stdout):
        LastScheduledRun.objects.create(
            name="check_coinbase_revocations",
            last_run=datetime(2024, 8, 1, 12, 0, 0, tzinfo=UTC),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"attestations": []}}
        mock_requests_post.return_value = mock_response

        call_command("check_coinbase_revocations", stdout=mock_stdout)

        last_run = LastScheduledRun.objects.get(name="check_coinbase_revocations")
        assert last_run.last_run == datetime(2024, 8, 1, 13, 0, 0, tzinfo=UTC)

        output = mock_stdout.getvalue()
        assert (
            "Checking for revoked attestations between [2024-08-01 12:00:00+00:00, 2024-08-01 13:00:00+00:00)"
            in output
        )
        assert "Found 0 revoked addresses" in output

    def test_api_error(self, mock_requests_post, mock_stdout):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests_post.return_value = mock_response

        with pytest.raises(
            Exception, match="Failed to query attestations: Internal Server Error"
        ):
            call_command("check_coinbase_revocations", stdout=mock_stdout)
