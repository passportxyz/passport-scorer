from django.test import TestCase
from django.test import Client

# Create your tests here.

from web3.auto import w3
from web3 import Web3
from eth_account.messages import encode_defunct
import binascii
import json
from datetime import datetime
from siwe import SiweMessage
from copy import deepcopy

def authenticate(client):
    """Test creation of an account wit SIWE"""
    web3 = Web3()
    web3.eth.account.enable_unaudited_hdwallet_features()
    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )
    print("account", account.address)

    c = Client()
    response = c.get("/account/nonce")

    data = response.json()
    print("Data", data)

    siwe_data = {
        "domain": "localhost",
        "address": account.address,
        "statement": "Sign in with Ethereum to the app.",
        "uri": "http://localhost/",
        "version": "1",
        "chainId": "1",
        "nonce": data["nonce"],
        "issuedAt": datetime.utcnow().isoformat(),
    }

    siwe_data_pay = deepcopy(siwe_data)
    siwe_data_pay["chain_id"] = siwe_data_pay["chainId"]
    siwe_data_pay["issued_at"] = siwe_data_pay["issuedAt"]

    siwe = SiweMessage(siwe_data_pay)
    data_to_sign = siwe.prepare_message()

    private_key = account.key
    signed_message = w3.eth.account.sign_message(
        encode_defunct(text=data_to_sign), private_key=private_key
    )

    response = c.post(
        "/account/verify",
        json.dumps(
            {
                "message": siwe_data,
                "signature": binascii.hexlify(signed_message.signature).decode(
                    "utf-8"
                ),
            }
        ),
        content_type="application/json",
    )
    return response, account, signed_message

class AccountTestCase(TestCase):
    def setUp(self):
        pass

    def test_create_account_with_SIWE(self):
        """Test creation of an account wit SIWE"""
        web3 = Web3()
        web3.eth.account.enable_unaudited_hdwallet_features()
        # TODO: load mnemonic from env
        my_mnemonic = (
            "chief loud snack trend chief net field husband vote message decide replace"
        )
        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        print("account", account.address)

        c = Client()
        response = c.get("/account/nonce")
        self.assertEqual(200, response.status_code)

        data = response.json()
        print("Data", data)

        siwe_data = {
            "domain": "localhost",
            "address": account.address,
            "statement": "Sign in with Ethereum to the app.",
            "uri": "http://localhost/",
            "version": "1",
            "chainId": "1",
            "nonce": data["nonce"],
            "issuedAt": datetime.utcnow().isoformat(),
        }

        siwe_data_pay = deepcopy(siwe_data)
        siwe_data_pay["chain_id"] = siwe_data_pay["chainId"]
        siwe_data_pay["issued_at"] = siwe_data_pay["issuedAt"]

        siwe = SiweMessage(siwe_data_pay)
        data_to_sign = siwe.prepare_message()

        private_key = account.key
        signed_message = w3.eth.account.sign_message(
            encode_defunct(text=data_to_sign), private_key=private_key
        )

        response = c.post(
            "/account/verify",
            json.dumps(
                {
                    "message": siwe_data,
                    "signature": binascii.hexlify(signed_message.signature).decode(
                        "utf-8"
                    ),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        # TODO: check payload of the JWT token ???
        self.assertTrue("refresh" in data)
        self.assertTrue("access" in data)

    def test_create_api_key(self):
        """Test creation of an API key"""
        client = Client()

        invalid_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer bad_token'})
        self.assertEqual(invalid_response.status_code, 401)


        # create api_key record
        response, account, signed_message = authenticate(client)
        access_token = response.json()['access']
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        self.assertEqual(api_key_response.status_code, 200)
        data = api_key_response.json()
        self.assertTrue("api_key" in data)

        # check that we are throwing a 401 if they have already created an account
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        self.assertEqual(api_key_response.status_code, 401)

    def test_get_api_keys(self):
        """Test getting API keys"""
        client = Client()

        invalid_response = client.get("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer invalid_token'})
        self.assertEqual(invalid_response.status_code, 401)
        
        response, account, signed_message = authenticate(client)
        access_token = response.json()['access']
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        api_key_response = client.post("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        
        valid_response = client.get("/account/api-key", content_type="application/json", **{'HTTP_AUTHORIZATION': f'Bearer {access_token}'})
        print(valid_response.json(), "valid_response")
        self.assertEqual(valid_response.status_code, 200)
        json_response = valid_response.json()
        self.assertEqual(len(json_response), 3)
        self.assertTrue("id" in json_response[0])
        self.assertTrue("id" in json_response[1])

