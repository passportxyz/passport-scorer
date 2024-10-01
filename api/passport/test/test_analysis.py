from unittest.mock import MagicMock, Mock, patch

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from web3 import Web3

from account.models import Account, AccountAPIKey
from aws_lambdas.passport.tests.test_passport_analysis_lambda import (
    mock_post_response,
    mock_post_response_with_failure,
)
from passport.api import (
    PassportAnalysisDetails,
    PassportAnalysisError,
    PassportAnalysisResponse,
    ScoreModel,
    handle_get_analysis,
)

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

User = get_user_model()


def assert_passport_analysis_structure(
    actual: PassportAnalysisResponse, expected: PassportAnalysisResponse
):
    assert actual.address == expected.address
    assert set(actual.details.models.keys()) == set(expected.details.models.keys())
    for model_name in expected.details.models:
        assert isinstance(actual.details.models[model_name], ScoreModel)
        assert isinstance(actual.details.models[model_name].score, (int, float))


@pytest.mark.django_db
class TestPassportAnalysis(TestCase):
    def setUp(self):
        user = User.objects.create(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        user_account = Account.objects.create(user=user, address=account.address)

        _obj, api_key = AccountAPIKey.objects.create_key(
            account=user_account,
            name="Token for user 1",
            analysis_rate_limit="100/30seconds",
        )

        self.headers = {"HTTP_X-API-Key": f"{api_key}"}
        self.client = Client()

    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_get_analysis_request(self, mock_post):
        """Test successfully requesting analysis through the API."""

        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=ethereum_activity",
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(analysis_response.status_code, 200)
        self.assertEqual(
            analysis_response.json(),
            {
                "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "details": {"models": {"ethereum_activity": {"score": 75}}},
            },
        )

    def test_bad_auth(self):
        headers = {"HTTP_X-API-Key": "bad_auth"}
        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=ethereum",
            content_type="application/json",
            **headers,
        )

        self.assertEqual(analysis_response.status_code, 401)

    def test_bad_address(self):
        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7d",
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(analysis_response.status_code, 400)

    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limit_is_applied(self):
        """
        Test that api rate limit is applied
        """
        client = Client()

        with patch("registry.api.utils.is_ratelimited", return_value=True):
            response = client.get(
                "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                **self.headers,
            )
            assert response.status_code == 429

    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_checksummed_address_is_passed_on(self, mock_post):
        """
        It is a requirement that the checksummed address is passed on in the requests to the model APIs.
        This is not enforced in the models.
        Changing this would affect the current cached values
        """
        self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7d?model_list=ethereum_activity".lower(),
            content_type="application/json",
            **self.headers,
        )

        # Verify that the address passed on is the checksummed address
        assert mock_post.call_args.args[2] == {
            "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D"
        }

    @override_settings(ONLY_ONE_MODEL=False)
    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_aggregate_model(self, mock_fetch):
        """Test aggregate model logic with prefetched_responses."""

        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=aggregate,ethereum_activity,nft",
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(
            analysis_response.json(),
            {
                "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "details": {
                    "models": {
                        "nft": {"score": 85},
                        "ethereum_activity": {"score": 75},
                        "aggregate": {"score": 90},
                    }
                },
            },
        )

        self.assertEqual(analysis_response.status_code, 200)

        # Should call once for each model involved in aggregation, once for aggregate,
        # and once for the NFT model. This means it is only calling ethereum_activity
        # once, even though it is involved in aggregation.
        expected_count = len(settings.MODEL_AGGREGATION_NAMES) + 2
        assert mock_fetch.call_count == expected_count

    @override_settings(ONLY_ONE_MODEL=False)
    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_ignore_duplicate_model(self, mock_fetch):
        """Test aggregate model logic with prefetched_responses."""

        analysis_response = self.client.get(
            "/passport/analysis/0x06e3c221011767FE816D0B8f5B16253E43e4Af7D?model_list=nft,nft",
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(
            analysis_response.json(),
            {
                "address": "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "details": {
                    "models": {
                        "nft": {"score": 85},
                    }
                },
            },
        )

        self.assertEqual(analysis_response.status_code, 200)

        assert mock_fetch.call_count == 1

    @override_settings(ONLY_ONE_MODEL=False)
    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_handle_get_analysis_returns_additional_data(self, mock_fetch):
        """Test handle_get_analysis returns additional data when requested."""
        analysis = async_to_sync(handle_get_analysis)(
            "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D", "zksync", False, True
        )

        assert analysis.details.models["zksync"].score == 95
        assert analysis.details.models["zksync"].num_transactions == 10
        assert analysis.details.models["zksync"].first_funder == "funder"
        assert analysis.details.models["zksync"].first_funder_amount == 1000

    @override_settings(ONLY_ONE_MODEL=False)
    @override_settings(NFT_MODEL_ENDPOINT="http://localhost:8123/eth-nft-predict")
    @override_settings(ZKSYNC_MODEL_ENDPOINT="http://localhost:8123/eth-zksync-predict")
    @patch("passport.api.fetch", side_effect=mock_post_response)
    def test_handle_get_analysis_does_not_return_additional_data(self, mock_fetch):
        """Test handle_get_analysis does not return additional data when not requested."""
        analysis = async_to_sync(handle_get_analysis)(
            "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D", "nft,zksync", False
        )
        expected = PassportAnalysisResponse(
            address="0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
            details=PassportAnalysisDetails(
                models={"nft": ScoreModel(score=85), "zksync": ScoreModel(score=0)}
            ),
        )

        assert_passport_analysis_structure(analysis, expected)

        # Check that additional data is not present
        for model_name in ["nft", "zksync"]:
            assert not hasattr(analysis.details.models[model_name], "n_transactions")
            assert not hasattr(analysis.details.models[model_name], "first_funder")
            assert not hasattr(
                analysis.details.models[model_name], "first_funder_amount"
            )

        # Check specific scores
        assert analysis.details.models["nft"].score == 85
        assert analysis.details.models["zksync"].score == 95

    @override_settings(ONLY_ONE_MODEL=False)
    @override_settings(NFT_MODEL_ENDPOINT="http://localhost:8123/eth-nft-predict")
    @override_settings(ZKSYNC_MODEL_ENDPOINT="http://localhost:8123/eth-zksync-predict")
    @patch("passport.api.fetch", side_effect=mock_post_response_with_failure("zksync"))
    def test_handle_get_analysis_when_one_model_fails(self, mock_fetch):
        """Test handle_get_analysis does not return additional data when not requested."""

        with pytest.raises(PassportAnalysisError) as exc_info:
            async_to_sync(handle_get_analysis)(
                "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D", "nft,zksync", False
            )
        assert '{"model": "zksync", "status": 500}' in exc_info.value.detail
        assert '{"model": "nft", "status": 200}' in exc_info.value.detail

    @override_settings(ONLY_ONE_MODEL=False)
    @override_settings(NFT_MODEL_ENDPOINT="http://localhost:8123/eth-nft-predict")
    @override_settings(ZKSYNC_MODEL_ENDPOINT="http://localhost:8123/eth-zksync-predict")
    @patch("passport.api.fetch", side_effect=mock_post_response_with_failure("zksync"))
    def test_handle_get_analysis_aggregate_when_one_model_fails(self, mock_fetch: Mock):
        """Test handle_get_analysis does return error when fetching data for at
        least one model fails."""

        with pytest.raises(PassportAnalysisError) as exc_info:
            async_to_sync(handle_get_analysis)(
                "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "nft,zksync,aggregate",
                False,
            )
        assert '{"model": "zksync", "status": 500}' in exc_info.value.detail
        assert '{"model": "nft", "status": 200}' in exc_info.value.detail
        assert mock_fetch.call_count == 2

    @override_settings(ONLY_ONE_MODEL=False)
    @override_settings(
        MODEL_ENDPOINTS={
            "ethereum_activity": "http://localhost:8123/ethereum_activity-predict",
            "zksync": "http://localhost:8123/eth-zksync-predict",
            "polygon": "http://localhost:8123/polygon-predict",
            "arbitrum": "http://localhost:8123/arbitrum-predict",
            "optimism": "http://localhost:8123/optimism-predict",
            "aggregate": "http://localhost:8123/aggregate",
        }
    )
    @patch("passport.api.fetch", side_effect=mock_post_response_with_failure("zksync"))
    def test_handle_get_analysis_when_only_aggregate_requested_and_submodule_fails(
        self, mock_fetch: Mock
    ):
        """Test handle_get_analysis returns erroor when only aggregate model is requiested,
        and getting a submodel data fails."""

        with pytest.raises(PassportAnalysisError) as exc_info:
            async_to_sync(handle_get_analysis)(
                "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D",
                "aggregate",  # only request the aggregate model
                False,
            )
        assert '{"model": "zksync", "status": 500}' in exc_info.value.detail
        assert '{"model": "optimism", "status": 200}' in exc_info.value.detail
        assert '{"model": "polygon", "status": 200}' in exc_info.value.detail
        assert '{"model": "arbitrum", "status": 200}' in exc_info.value.detail
        assert '{"model": "ethereum_activity", "status": 200}' in exc_info.value.detail
        assert mock_fetch.call_count == 5
