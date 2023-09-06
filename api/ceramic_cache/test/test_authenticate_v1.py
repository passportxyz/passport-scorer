import copy
import json
from collections import namedtuple

import pytest
from account.models import Nonce
from django.test import Client
from ninja_jwt.tokens import AccessToken

pytestmark = pytest.mark.django_db

client = Client()

# The sample payload contains dummy cid, cacao and issuer as they are not relevant for this test
# and valid nonce & paylod => this should be valided in the authenticate handler
sample_authenticate_payload = {
    "signatures": [
        {
            "protected": "eyJhbGciOiJFZERTQSIsImNhcCI6ImlwZnM6Ly9iYWZ5cmVpZmhkYTQ2eWp5NWRhYWxocXh2anZvcnpqdnlleHp1bjRrcWRmZWU0YnkybmJyNWhzcHd1eSIsImtpZCI6ImRpZDprZXk6ejZNa2pHSGtRNDVpY3BSakdqWUhWWUZLTkpDMTdwbnE0UU04UWJuODhLSEVaQ05XI3o2TWtqR0hrUTQ1aWNwUmpHallIVllGS05KQzE3cG5xNFFNOFFibjg4S0hFWkNOVyJ9",
            "signature": "UmVH-NMdgn-P-VE0ejTlmrRxbF45W20Q9SfIThqODF9USwzxFi3kceDttlBWwNZkrGogdqm-SdJQdoRC0GYSCA",
        }
    ],
    "payload": "AXESIJ-t3oi3FWOnXzz1JomHf4BeT-DVOaW5-RtZGPf_miHs",
    "cid": [
        1,
        113,
        18,
    ],
    "cacao": [163, 97, 104],
    "issuer": "did:pkh:eip155:1:0xffffffffffffffffffffffffffffffffffffffff",
    "nonce": "TODO - add unique nonce here",
}


class TestAuthenticate:
    base_url = "/ceramic-cache"

    def test_authenticate_validates_payload(self, mocker):
        """
        We expect that the authenticate request:
        1. validates the payload against the nonce
        2. makes a validation request for the dagJWS to the verifier

        If both are ok, the test should succeed
        """
        MockedRequestResponse = namedtuple("MockedRequestResponse", "status_code")
        with mocker.patch(
            "ceramic_cache.api.v1.requests.post",
            return_value=MockedRequestResponse(200),
        ):
            with mocker.patch(
                "ceramic_cache.api.v1.validate_dag_jws_payload", return_value=True
            ):
                payload = copy.deepcopy(sample_authenticate_payload)
                payload["nonce"] = Nonce.create_nonce().nonce

                auth_response = client.post(
                    f"{self.base_url}/authenticate",
                    json.dumps(payload),
                    content_type="application/json",
                )

                json_data = auth_response.json()

                assert auth_response.status_code == 200
                assert "access" in json_data

                token = AccessToken(json_data["access"])
                assert token["did"] == payload["issuer"]

    def test_authenticate_fails_to_validate_invalid_payload(self, mocker):
        """
        We expect that the authenticate request:
        1. validates the payload against the nonce
        2. makes a validation request for the dagJWS to the verifier

        The test should fail at step 1 as we will corupt the payload
        """
        with mocker.patch(
            "ceramic_cache.api.v1.validate_dag_jws_payload", return_value=False
        ):
            auth_response = client.post(
                f"{self.base_url}/authenticate",
                json.dumps(sample_authenticate_payload),
                content_type="application/json",
                # **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
            )

            json_data = auth_response.json()

            assert auth_response.status_code == 400
            assert "detail" in json_data
            assert json_data["detail"] == "Invalid nonce or payload!"

    def test_authenticate_fails_when_validating_payload_throws(self, mocker):
        """
        We expect that the authenticate request:
        1. validates the payload against the nonce
        2. makes a validation request for the dagJWS to the verifier

        The test should fail at step 1 if the validate_dag_jws_payload throws
        """

        with mocker.patch(
            "ceramic_cache.api.v1.validate_dag_jws_payload",
            side_effect=Exception("something bad happened"),
        ):
            auth_response = client.post(
                f"{self.base_url}/authenticate",
                json.dumps(sample_authenticate_payload),
                content_type="application/json",
                # **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
            )

            json_data = auth_response.json()

            assert auth_response.status_code == 400
            assert "detail" in json_data
            assert json_data["detail"] == "Invalid nonce or payload!"

    def test_authenticate_fails_when_validating_jws_fails(self, mocker):
        """
        We expect that the authenticate request:
        1. validates the payload against the nonce
        2. makes a validation request for the dagJWS to the verifier

        The test should fail at step 2 if the validation returns anything other than 200
        """

        MockedRequestResponse = namedtuple("MockedRequestResponse", "status_code text")
        with mocker.patch(
            "ceramic_cache.api.v1.requests.post",
            return_value=MockedRequestResponse(400, "this failed"),
        ):
            with mocker.patch(
                "ceramic_cache.api.v1.validate_dag_jws_payload", return_value=True
            ):
                payload = copy.deepcopy(sample_authenticate_payload)
                payload["nonce"] = Nonce.create_nonce().nonce
                auth_response = client.post(
                    f"{self.base_url}/authenticate",
                    json.dumps(payload),
                    content_type="application/json",
                )

                json_data = auth_response.json()

                assert auth_response.status_code == 400

                assert "detail" in json_data
                assert json_data["detail"].startswith("Verifier response")

    def test_authenticate_fails_when_validating_jws_throws(self, mocker):
        """
        We expect that the authenticate request:
        1. validates the payload against the nonce
        2. makes a validation request for the dagJWS to the verifier

        The test should fail at step 2 if the validation throws
        """

        with mocker.patch(
            "ceramic_cache.api.v1.requests.post",
            side_effect=Exception("this is broken"),
        ):
            with mocker.patch(
                "ceramic_cache.api.v1.validate_dag_jws_payload", return_value=True
            ):
                payload = copy.deepcopy(sample_authenticate_payload)
                payload["nonce"] = Nonce.create_nonce().nonce
                auth_response = client.post(
                    f"{self.base_url}/authenticate",
                    json.dumps(payload),
                    content_type="application/json",
                )

                json_data = auth_response.json()
                assert auth_response.status_code == 500

                assert "detail" in json_data
                assert json_data["detail"].startswith("Failed authenticate request")
