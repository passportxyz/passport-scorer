import pytest
from account.models import Account, AccountAPIKey, Community
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from registry.models import Passport, Score
from web3 import Web3

User = get_user_model()
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

pytestmark = pytest.mark.django_db


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
            f"/registry/score/{additional_community.pk}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 0

    def test_get_scores_returns_first_page_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        offset = 0
        limit = 2

        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?limit={limit}&offset={offset}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200

        for i in range(0, 1):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[offset + i]["address"].lower()
            )

    def test_get_scores_returns_second_page_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        offset = 2
        limit = 2

        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?limit={limit}&offset={offset}",
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
            f"/registry/score/3",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        # assert response.status_code == 404
        assert response.json() == {
            "detail": "No Community matches the given query.",
        }

    def test_get_single_score_for_address(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?address={passport_holder_addresses[0]['address']}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200

        assert (
            response.json()["items"][0]["address"]
            == passport_holder_addresses[0]["address"].lower()
        )

    def test_get_single_score_for_address_in_path(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}/{passport_holder_addresses[0]['address']}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200

        assert (
            response.json()["address"]
            == passport_holder_addresses[0]["address"].lower()
        )

    def test_get_single_score_for_address_in_path_for_other_community(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        """
        Test that a user can't get scores for a community they don't belong to.
        """
        # Create another user, account & api key
        user = User.objects.create_user(username="anoter-test-user", password="12345")
        web3_account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        account = Account.objects.create(user=user, address=web3_account.address)
        (_, api_key) = AccountAPIKey.objects.create_key(
            account=account, name="Token for user 1"
        )

        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}/{passport_holder_addresses[0]['address']}",
            HTTP_AUTHORIZATION="Token " + api_key,
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "No Community matches the given query."}

    def test_limit_greater_than_1000_throws_an_error(
        self, scorer_community, passport_holder_addresses, scorer_api_key
    ):
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?limit=1001",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Invalid limit.",
        }

    def test_limit_of_1000_is_ok(
        self, scorer_community, passport_holder_addresses, scorer_api_key
    ):
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?limit=1000",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200

    def test_get_score_for_other_community(self, scorer_community, scorer_api_key):
        """Test that a user can't get scores for a community they don't belong to."""
        # Create another user, account & api key
        user = User.objects.create_user(username="anoter-test-user", password="12345")
        web3_account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )

        account = Account.objects.create(user=user, address=web3_account.address)
        (_, api_key) = AccountAPIKey.objects.create_key(
            account=account, name="Token for user 1"
        )

        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?limit=1000",
            HTTP_AUTHORIZATION="Token " + api_key,
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "No Community matches the given query."}

    def test_get_scores_request_throws_403_for_non_researcher(self, scorer_api_key):
        client = Client()
        response = client.get(
            f"/analytics/score/",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 403
        assert response.json() == {
            "detail": "You are not allowed to access this endpoint.",
        }

    def test_get_first_page_scores_for_researcher(
        self,
        scorer_api_key,
        scorer_account,
        passport_holder_addresses,
        paginated_scores,
    ):
        group, _ = Group.objects.get_or_create(name="Researcher")
        scorer_account.user.groups.add(group)

        limit = 2

        client = Client()
        response = client.get(
            f"/analytics/score/?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()

        assert response.status_code == 200
        assert response_data["next"] == f"/analytics/score/?last_id=2"
        for i in range(0, 1):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[i]["address"].lower()
            )

    def test_get_second_page_scores_for_researcher(
        self,
        scorer_api_key,
        scorer_account,
        passport_holder_addresses,
        paginated_scores,
    ):
        group, _ = Group.objects.get_or_create(name="Researcher")
        scorer_account.user.groups.add(group)

        last_id = 2
        limit = 2

        client = Client()
        response = client.get(
            f"/analytics/score/?limit={limit}&last_id={last_id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()

        assert response.status_code == 200
        assert response_data["next"] == f"/analytics/score/?last_id=4"
        for i in range(0, 1):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[last_id + i]["address"].lower()
            )

    def test_get_first_page_scores_by_community_id_for_researcher(
        self,
        scorer_api_key,
        scorer_account,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        group, _ = Group.objects.get_or_create(name="Researcher")
        scorer_account.user.groups.add(group)

        limit = 2

        client = Client()
        response = client.get(
            f"/analytics/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert (
            response_data["next"] == f"/analytics/score/{scorer_community.id}?last_id=2"
        )

        for i in range(0, 1):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[i]["address"].lower()
            )

    def test_get_second_page_scores_by_community_id_for_researcher(
        self,
        scorer_api_key,
        scorer_account,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        group, _ = Group.objects.get_or_create(name="Researcher")
        scorer_account.user.groups.add(group)

        last_id = 2
        limit = 2

        client = Client()
        response = client.get(
            f"/analytics/score/{scorer_community.id}?limit={limit}&last_id={last_id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert (
            response_data["next"] == f"/analytics/score/{scorer_community.id}?last_id=4"
        )

        for i in range(0, 1):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[last_id + i]["address"].lower()
            )
