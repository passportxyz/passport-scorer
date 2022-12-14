import json
from sysconfig import get_default_scheme
import pytest
from account.models import Account, Community, get_default_community_scorer
from django.contrib.auth.models import User
from django.test import Client
from web3 import Web3
from ninja_jwt.schema import RefreshToken

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
        labels = [i[1] for i in scorer.Type.choices]
        ids = [i[0] for i in scorer.Type.choices]
        client = Client()
        response = client.get(
            f"/account/communities/{scorer_community.id}/scorers",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
            "current_scorer": scorer.type,
            "labels": labels,
            "ids": ids,
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
        labels = [i[1] for i in scorer.Type.choices]
        ids = [i[0] for i in scorer.Type.choices]
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
        labels = [i[1] for i in scorer.Type.choices]
        ids = [i[0] for i in scorer.Type.choices]
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
