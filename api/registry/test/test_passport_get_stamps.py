from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from web3 import Web3

from ceramic_cache.models import CeramicCache
from registry.api.v1 import fetch_stamp_metadata_for_provider

User = get_user_model()
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

pytestmark = pytest.mark.django_db

mock_stamp_metadata = [
    {
        "id": "TestPlatform",
        "name": "Test Platform",
        "icon": "assets/test.svg",
        "description": "Platform for testing",
        "connectMessage": "Verify Account",
        "groups": [
            {
                "name": "Test",
                "stamps": [
                    {
                        "name": f"Provider{i}",
                        "description": "Tested",
                        "hash": "0xb03cac9e8f0914ebb46e62ddee5a8337dcf4cdf6284173ebfb4aa777d5f481be",
                    }
                    for i in range(10)
                ],
            }
        ],
    }
]


@pytest.fixture
def paginated_stamps(scorer_community, passport_holder_addresses):
    address = passport_holder_addresses[0]["address"]

    stamps = []

    for i in range(10):
        provider = f"Provider{i}"
        cacheStamp = CeramicCache.objects.create(
            address=address,
            provider=provider,
            stamp={
                "type": ["VerifiableCredential"],
                "proof": {
                    "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..34uD8jKn2N_yE8pY4ErzVD8pJruZq7qJaCxx8y0SReY2liZJatfeQUv1nqmZH19a-svOyfHt_VbmKvh6A5vwBw",
                    "type": "Ed25519Signature2018",
                    "created": "2023-01-24T00:55:02.028Z",
                    "proofPurpose": "assertionMethod",
                    "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
                },
                "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
                "@context": ["https://www.w3.org/2018/credentials/v1"],
                "issuanceDate": "2023-01-24T00:55:02.028Z",
                "expirationDate": "2023-04-24T00:55:02.028Z",
                "credentialSubject": {
                    "id": "did:pkh:eip155:1:0xf4c5c4deDde7A86b25E7430796441e209e23eBFB",
                    "hash": "v0.0.0:Ft7mqRdvJ9jNgSSowb9qdcMeOzswOeighIOvk0wn964=",
                    "@context": [
                        {
                            "hash": "https://schema.org/Text",
                            "provider": "https://schema.org/Text",
                        }
                    ],
                    "provider": provider,
                },
            },
        )
        stamps.append(cacheStamp)

    return stamps


class TestPassportGetStamps:
    base_url = "/registry"

    def test_get_stamps_with_address_with_no_scores(
        self, scorer_api_key, passport_holder_addresses
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == 0

    def test_get_stamps_only_includes_this_address(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
    ):
        paginated_stamps.reverse()
        last_stamp = paginated_stamps[-1]

        # Add another stamp with a different address
        CeramicCache.objects.create(
            address=passport_holder_addresses[1]["address"],
            provider=last_stamp.provider,
            stamp=last_stamp.stamp,
        )

        limit = 20

        client = Client()
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200

        response_data = response.json()
        assert len(response_data["items"]) == len(paginated_stamps)

        assert len(CeramicCache.objects.all()) == len(paginated_stamps) + 1

    def test_include_metadata(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
        mocker,
    ):
        cache.clear()
        mocker.patch(
            "requests.get", return_value=mocker.Mock(json=lambda: mock_stamp_metadata)
        )
        client = Client()
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?include_metadata=true&limit=1",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["items"][0]["metadata"]["name"] == f"Provider9"

    def test_fetch_stamp_metadata_for_invalid_provider_returns_none(
        self,
        mocker,
    ):
        cache.clear()
        mocker.patch(
            "requests.get", return_value=mocker.Mock(json=lambda: mock_stamp_metadata)
        )
        assert fetch_stamp_metadata_for_provider("invalid_provider") is None

    def test_get_all_metadata(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
        mocker,
    ):
        cache.clear()
        mocker.patch(
            "requests.get", return_value=mocker.Mock(json=lambda: mock_stamp_metadata)
        )
        client = Client()
        response = client.get(
            f"{self.base_url}/stamp-metadata",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data[0]["id"] == mock_stamp_metadata[0]["id"]
        assert (
            response_data[0]["groups"][0]["stamps"][0]["name"]
            == mock_stamp_metadata[0]["groups"][0]["stamps"][0]["name"]
        )
        assert mock_stamp_metadata[0]["icon"] in response_data[0]["icon"]
        assert mock_stamp_metadata[0]["icon"] != response_data[0]["icon"]

    def test_get_stamps_returns_first_page_stamps(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
    ):
        paginated_stamps.reverse()
        limit = 2

        client = Client()
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200

        assert response_data["prev"] == None

        next_page = client.get(
            response_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert next_page.status_code == 200

        next_page_prev = client.get(
            next_page.json()["prev"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert next_page_prev.status_code == 200

        assert next_page_prev.json() == response_data

        for i in range(limit):
            assert (
                response_data["items"][i]["credential"]["credentialSubject"]["provider"]
                == paginated_stamps[
                    i
                ].provider  # reversed order since get stamps is descending
            )

    def test_get_stamps_returns_second_page_stamps(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
    ):
        paginated_stamps.reverse()
        limit = 2

        client = Client()
        page_one_response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_one_data = page_one_response.json()

        assert page_one_response.status_code == 200

        page_two_response = client.get(
            page_one_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_two_data = page_two_response.json()

        assert page_two_response.status_code == 200

        page_two_prev = client.get(
            page_two_data["prev"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert page_two_prev.status_code == 200

        assert page_two_prev.json() == page_one_data

        for i in range(limit):
            assert (
                page_two_data["items"][i]["credential"]["credentialSubject"]["provider"]
                == paginated_stamps[i + limit].provider
            )

    def test_get_stamps_returns_third_page_stamps(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
    ):
        paginated_stamps.reverse()
        limit = 2

        client = Client()

        page_one_response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_one_data = page_one_response.json()

        assert page_one_response.status_code == 200

        page_two_response = client.get(
            page_one_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_two_data = page_two_response.json()

        assert page_two_response.status_code == 200

        page_three_response = client.get(
            page_two_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_three_data = page_three_response.json()

        assert page_three_response.status_code == 200

        page_three_prev = client.get(
            page_three_data["prev"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert page_three_prev.status_code == 200

        assert page_three_prev.json() == page_two_data

        for i in range(limit):
            assert (
                page_three_data["items"][i]["credential"]["credentialSubject"][
                    "provider"
                ]
                == paginated_stamps[i + limit * 2].provider
            )

    def test_limit_greater_than_1000_throws_an_error(
        self, passport_holder_addresses, scorer_api_key
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit=1001",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Invalid limit.",
        }

    def test_limit_of_1000_is_ok(self, passport_holder_addresses, scorer_api_key):
        client = Client()
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit=1000",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200

    def test_get_last_page_stamps_by_address(
        self,
        scorer_api_key,
        passport_holder_addresses,
        paginated_stamps,
    ):
        """
        We will try reading all stamps in 2 request (2 batches). We expect the next link after the 1st page to be valid,
        and the second page to be null.
        """

        paginated_stamps.reverse()

        num_stamps = len(paginated_stamps)

        limit = int(num_stamps / 2)
        client = Client()

        # Read the 1st batch
        response = client.get(
            f"{self.base_url}/stamps/{passport_holder_addresses[0]['address']}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == limit
        assert len(response_data["next"]) != None

        # Read the 2nd batch
        response = client.get(
            response_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert len(response_data["items"]) == len(paginated_stamps) - limit
        assert response_data["next"] == None
