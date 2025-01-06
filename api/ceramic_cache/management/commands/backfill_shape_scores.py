from django.core.management.base import BaseCommand, CommandError
import os
import csv
import requests
from web3 import Web3
from eth_account import Account
from typing import List, Dict, Any
from ceramic_cache.models import CeramicCache
import traceback


SHAPE_CHAIN_ID = "0x168"
CUSTOM_SCORER_ID = 7922
IAM_EAS_ENDPOINT = "https://iam.passport.xyz/api/v0.0.0/eas/passport"
GITCOIN_ATTESTER_ADDRESS = "0xCc90105D4A2aa067ee768120AdA19886021dF422"
GITCOIN_ATTESTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "schema", "type": "bytes32"},
                    {
                        "components": [
                            {
                                "internalType": "address",
                                "name": "recipient",
                                "type": "address",
                            },
                            {
                                "internalType": "uint64",
                                "name": "expirationTime",
                                "type": "uint64",
                            },
                            {
                                "internalType": "bool",
                                "name": "revocable",
                                "type": "bool",
                            },
                            {
                                "internalType": "bytes32",
                                "name": "refUID",
                                "type": "bytes32",
                            },
                            {"internalType": "bytes", "name": "data", "type": "bytes"},
                            {
                                "internalType": "uint256",
                                "name": "value",
                                "type": "uint256",
                            },
                        ],
                        "internalType": "struct AttestationRequestData[]",
                        "name": "data",
                        "type": "tuple[]",
                    },
                ],
                "internalType": "struct MultiAttestationRequest[]",
                "name": "multiAttestationRequest",
                "type": "tuple[]",
            }
        ],
        "name": "submitAttestations",
        "outputs": [{"internalType": "bytes32[]", "name": "", "type": "bytes32[]"}],
        "stateMutability": "payable",
        "type": "function",
    },
]


class Command(BaseCommand):
    help = "Submit attestations for addresses from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "input",
            type=str,
            help="Path to CSV file containing addresses and submit_onchain flags",
        )

    def __init__(self):
        super().__init__()
        rpc_url = os.environ.get("SHAPE_RPC_URL")
        if not rpc_url:
            raise ValueError("SHAPE_RPC_URL environment variable not set")
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        private_key = os.environ.get("PRIVATE_KEY")
        if not private_key:
            raise ValueError("PRIVATE_KEY environment variable not set")
        self.account = Account.from_key(private_key)
        print(f"Using account address: {self.account.address}")

        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(GITCOIN_ATTESTER_ADDRESS),
            abi=GITCOIN_ATTESTER_ABI,
        )

    def get_user_credentials(self, address: str) -> List[Dict]:
        """Fetch user credentials from CeramicCache"""
        cached_stamps = CeramicCache.objects.filter(
            address=address,
            type=CeramicCache.StampType.V1,
            deleted_at__isnull=True,
            revocation__isnull=True,
        )
        return [c.stamp for c in cached_stamps]

    def get_attestation_data(
        self, address: str, credentials: List[Dict]
    ) -> Dict[str, Any]:
        """Get attestation data from IAM endpoint"""
        payload = {
            "nonce": 1,
            "recipient": address,
            "credentials": credentials,
            "chainIdHex": SHAPE_CHAIN_ID,
            "customScorerId": CUSTOM_SCORER_ID,
        }

        response = requests.post(IAM_EAS_ENDPOINT, json=payload)
        if response.status_code != 200:
            raise Exception(f"IAM request failed: {response.text}")

        return response.json()["passport"]

    def submit_attestation(self, attestation_request: Dict) -> str:
        """Submit attestation to the blockchain"""
        for multiAttestationRequest in attestation_request["multiAttestationRequest"]:
            for attestationRequestData in multiAttestationRequest["data"]:
                attestationRequestData["expirationTime"] = int(
                    attestationRequestData["expirationTime"]
                )
                attestationRequestData["value"] = int(attestationRequestData["value"])
        # Prepare transaction
        tx = self.contract.functions.submitAttestations(
            attestation_request["multiAttestationRequest"]
        ).build_transaction(
            {
                "from": self.account.address,
            }
        )
        # Sign and send transaction
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        # Wait for transaction receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt["transactionHash"].hex()

    def handle(self, *args, **options):
        csv_path = options["input"]

        if not os.path.exists(csv_path):
            raise CommandError(f"CSV file not found: {csv_path}")

        with open(csv_path, "r") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                address = self.w3.to_checksum_address(row["address"])
                submit_onchain = row["submit_onchain"].lower() == "true"

                try:
                    self.stdout.write(f"Processing address: {address}")

                    # Get user credentials
                    credentials = self.get_user_credentials(address)
                    if not credentials:
                        self.stdout.write(f"No credentials found for {address}")
                        continue

                    # Get attestation data from IAM
                    attestation_data = self.get_attestation_data(address, credentials)

                    if submit_onchain:
                        # Submit attestation only if submit_onchain is true
                        tx_hash = self.submit_attestation(attestation_data)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully submitted attestation for {address}. "
                                f"Transaction hash: {tx_hash}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Skipped onchain submission for {address} as requested"
                            )
                        )

                except Exception as e:
                    error_message = traceback.format_exc()
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error processing address {address}: {error_message}"
                        )
                    )
