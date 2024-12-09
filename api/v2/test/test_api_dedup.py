from datetime import datetime, timedelta
from re import M
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from web3 import Web3

from account.models import Account, AccountAPIKey, Community
from ceramic_cache.models import CeramicCache
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.config.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer_weighted.models import BinaryWeightedScorer, Scorer, WeightedScorer

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()


pytestmark = pytest.mark.django_db
my_mnemonic = settings.TEST_MNEMONIC
wallet_a = web3.eth.account.from_mnemonic(
    my_mnemonic, account_path="m/44'/60'/0'/0/0"
).address
wallet_b = web3.eth.account.from_mnemonic(
    my_mnemonic, account_path="m/44'/60'/0'/0/0"
).address


class TestApiGetStampsDedupFlagTestCase:
    base_url = "/v2/stamps"

    @patch("registry.atasks.validate_credential", side_effect=[[], []])
    def test_get_stamps_no_dedup(self, validate_credential, weight_config):
        """
        Test get stamps for user with no deduplication
        """

        client = Client()
        sample_provider = "LinkedinV2"
        now = datetime.now()
        days_ago = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        days_later = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # # Create a comunity
        user = User.objects.create_user(username="user", password="userpwd")
        account = Account.objects.create(user=user, address=wallet_a)
        _scorer = WeightedScorer.objects.create(type=Scorer.Type.WEIGHTED)

        comunity = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=account,
            scorer=_scorer,
        )

        (_, api_key) = AccountAPIKey.objects.create_key(
            account=account,
            name="Token for user 1",
            rate_limit="3/30seconds",
            analysis_rate_limit="3/30seconds",
            historical_endpoint=True,
        )
        # check :

        # config = WeightConfiguration.objects.create(
        #     version="v2",
        #     threshold=20.0,
        #     active=True,
        #     description="Test",
        # )

        # for provider, weight in GITCOIN_PASSPORT_WEIGHTS.items():
        #     WeightConfigurationItem.objects.create(
        #         weight_configuration=config,
        #         provider=provider,
        #         weight=float(weight),
        #     )

        # Create a stamp
        CeramicCache.objects.create(
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
                    "hash": "v0.0.0:Ft7mqRdvJ9jNgSSowb9qdcMeOzswOeighIOvk0wn964=",
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

        response = client.get(
            f"{self.base_url}/{comunity.pk}/score/{wallet_a}",
            HTTP_AUTHORIZATION="Token " + api_key,
        )
        response_data = response.json()
        print("response_data 123123", response_data)
        assert response.status_code == 200
        assert response_data["error"] is None
        assert int(response_data["score"]) > 0
        assert response_data["stamps"] == {
            sample_provider: {
                "score": "1.00",  # TODO : ???
                "dedup": False,
                "expiration_date": days_later,
            }
        }
