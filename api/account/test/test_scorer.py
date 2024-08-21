import json

import pytest
from django.conf import settings
from django.test import Client
from web3 import Web3

from account.models import Community
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer_weighted.models import Scorer, get_default_threshold

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db

my_mnemonic = settings.TEST_MNEMONIC


class TestScorer:
    def test_get_default_scorer(self, client, access_token, scorer_community):
        scorer = scorer_community.scorer
        scorers = [{"id": i[0], "label": i[1]} for i in scorer.Type.choices]
        client = Client()
        response = client.get(
            f"/account/communities/{scorer_community.id}/scorers",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
            "current_scorer": scorer.type,
            "scorers": scorers,
        }

    def test_unauthorized_get_default_scorer(self, client, scorer_community):
        client = Client()
        response = client.get(
            f"/account/communities/{scorer_community.id}/scorers",
            HTTP_AUTHORIZATION="Bearer badtoken",
        )
        assert response.status_code == 401

    def test_update_community_scorer(self, client, access_token, scorer_community):
        scorer = scorer_community.scorer
        client = Client()
        response = client.put(
            f"/account/communities/{scorer_community.id}/scorers",
            json.dumps({"scorer_type": scorer.Type.WEIGHTED_BINARY}),
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
        }

    def test_do_not_allow_unauthorized_scorer_update(self, client, scorer_community):
        scorer = scorer_community.scorer
        client = Client()
        response = client.put(
            f"/account/communities/{scorer_community.id}/scorers",
            json.dumps({"scorer_type": scorer.Type.WEIGHTED_BINARY}),
            HTTP_AUTHORIZATION=f"Bearer badtoken",
        )

        assert response.status_code == 401

    def test_do_not_allow_invalid_scorer_type_update(
        self, client, access_token, scorer_community
    ):
        client = Client()
        response = client.put(
            f"/account/communities/{scorer_community.id}/scorers",
            json.dumps({"scorer_type": "Christmas"}),
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == 400

    def test_update_to_weighted_to_binary(self, client, access_token, scorer_community):
        scorer = scorer_community.scorer
        client = Client()
        response = client.put(
            f"/account/communities/{scorer_community.id}/scorers",
            json.dumps({"scorer_type": scorer.Type.WEIGHTED_BINARY}),
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
        }

        # Test that the changes have been persisted in the DB
        community = Community.objects.get(pk=scorer_community.id)
        scorer = Scorer.objects.get(pk=community.scorer_id)
        assert scorer.type == Scorer.Type.WEIGHTED_BINARY
        # Ensure the default threshold was set
        assert scorer.binaryweightedscorer.threshold == get_default_threshold()
