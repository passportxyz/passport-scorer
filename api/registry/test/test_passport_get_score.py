import pytest
from account.models import Account, AccountAPIKey, Community
from django.test import Client
from registry.models import Passport, Score, Stamp
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

# TODO: Load from fixture file
pytestmark = pytest.mark.django_db

offset = 2
limit = 4


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
def scorer_api_key(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Token for user 1"
    )
    return secret


@pytest.fixture
def scorer_passport(scorer_account, scorer_community):
    passport = Passport.objects.create(
        address=scorer_account.address,
        passport={"name": "John Doe"},
        community=scorer_community,
    )
    return passport


@pytest.fixture
def scorer_score(scorer_passport):
    stamp = Score.objects.create(
        passport=scorer_passport,
        score="0.650000000",
    )
    return stamp


@pytest.fixture
def paginated_scores(scorer_passport, passport_holder_addresses, scorer_community):
    scores = []
    for holder in passport_holder_addresses:
        passport = Passport.objects.create(
            address=holder["address"],
            community=scorer_community,
            passport={"name": "John Doe"},
        )

        score = Score.objects.create(
            passport=passport,
            score="1",
        )

        scores.append(score)
    return scores


class TestPassportGetScore:
    def test_passport_get_scores(
        self, scorer_api_key, scorer_community, scorer_account, scorer_score
    ):
        address = scorer_account.address
        community_id = scorer_community.id
        client = Client()
        response = client.get(
            f"/registry/score/{community_id}/{address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200
        assert response.json() == {
            "address": address.lower(),
            "score": scorer_score.score,
        }

    # TODO: Create test authorization separately
    def test_passport_get_scores_no_auth(self, scorer_community, scorer_account):
        address = scorer_account.address
        community_id = scorer_community.id
        client = Client()
        response = client.get(
            f"/registry/score/{community_id}/{address}",
        )
        assert response.status_code == 401

    def test_passport_get_scores_bad_community(self, scorer_api_key, scorer_account):
        address = scorer_account.address
        client = Client()
        response = client.get(
            f"/registry/score/3/{address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 400

    def test_get_score_with_valid_community_with_no_scores(
        self, scorer_api_key, scorer_account
    ):
        additional_community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=scorer_account,
        )

        address = scorer_account.address
        client = Client()
        response = client.get(
            f"/registry/score/{additional_community.id}/{address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 400

    def test_get_scores_with_valid_community_with_no_scores(
        self, scorer_api_key, scorer_account
    ):
        additional_community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=scorer_account,
        )

        client = Client()
        response = client.get(
            f"/registry/scores/{additional_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 0

    def test_get_scores_returns_second_page_scores(
        self,
        scorer_api_key,
        scorer_account,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        address = scorer_account.address
        client = Client()
        response = client.get(
            f"/registry/scores/{scorer_community.id}?limit={limit}&offset={offset}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200

        for i in range(0, 2):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[offset + i]["address"].lower()
            )

    def test_get_scores_request_throws_400_for_invalid_community(self, scorer_api_key):
        client = Client()
        response = client.get(
            f"/registry/scores/3",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Unable to get score for provided community.",
        }

    def test_get_single_score_for_address(
        self,
        scorer_api_key,
        scorer_account,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        client = Client()
        response = client.get(
            f"/registry/scores/{scorer_community.id}?address={passport_holder_addresses[0]['address']}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200

        assert (
            response.json()["items"][0]["address"]
            == passport_holder_addresses[0]["address"].lower()
        )
