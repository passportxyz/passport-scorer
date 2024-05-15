import asyncio
import base64
import json
from random import choice
from secrets import token_bytes

import didkit
from config import providers
from web3 import Web3
import os

w3 = Web3()

JWK = os.environ["JWK"]
num_accounts = int(os.environ["NUM_ACCOUNTS"])

accounts_file = f"generated_accounts_{num_accounts}.json"

with open(accounts_file) as f:
    addresses = json.load(f)

num_total_accounts = len(addresses)
print("Num accounts:", num_total_accounts)


async def main():
    generated_vcs = []

    did = didkit.key_to_did("key", JWK)
    verification_method = await didkit.key_to_verification_method("key", JWK)
    options = {
        "proofPurpose": "assertionMethod",
        "verificationMethod": verification_method,
    }

    print("issuer: ", did)

    async def issue_vc(crdential):
        vc = await didkit.issue_credential(
            json.dumps(credential), json.dumps(options), JWK
        )
        return vc

    _count = -1
    for i in range(num_total_accounts):
        address = addresses[i]
        generated_vcs = []
        for j in range(20):
            _count += 1
            print(f"Issuing VC: {_count}")
            credential = {
                "type": ["VerifiableCredential"],
                "issuer": did,
                "@context": ["https://www.w3.org/2018/credentials/v1"],
                "issuanceDate": "2022-07-19T10:42:24.883Z",
                "expirationDate": "2222-12-31T23:59:59.999Z",
                "credentialSubject": {
                    "@context": {
                        "hash": "https://schema.org/Text",
                        "provider": "https://schema.org/Text",
                    },
                    "id": f"did:pkh:eip155:1:{addresses[i]}",
                    "hash": f"v9000.0.0:{base64.b64encode(token_bytes(32)).decode('utf-8')}",
                    "provider": choice(providers),
                },
            }
            vc = json.loads(await issue_vc(credential))
            generated_vcs.append(vc)

        filename = f"./vcs/{address}_vcs.json"
        with open(filename, "w") as f:
            f.write(json.dumps(generated_vcs))


asyncio.run(main())
