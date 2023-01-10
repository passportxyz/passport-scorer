import json
from sysconfig import get_default_scheme

import pytest
from account.models import Account, Community
from django.contrib.auth.models import User
from django.test import Client
from ninja_jwt.schema import RefreshToken
from scorer_weighted.models import Scorer, get_default_threshold
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

# TODO: Load from fixture file
pytestmark = pytest.mark.django_db


@pytest.fixture
def scorer_user():
    user = User.objects.create_user(username="testuser-1", password="12345")
    return user


@pytest.fixture
def scorer_account(scorer_user):
    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    print("scorer_user", scorer_user)
    print("web3_account.address", web3_account.address)
    account = Account.objects.create(user=scorer_user, address=web3_account.address)
    return account


@pytest.fixture
def scorer_community(scorer_account):
    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
    )
    return community


@pytest.fixture
def access_token(scorer_user):
    refresh = RefreshToken.for_user(scorer_user)
    return refresh.access_token


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
