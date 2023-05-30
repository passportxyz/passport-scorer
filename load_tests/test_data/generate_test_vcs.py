import asyncio
import base64
import hashlib
import json
import sys
from copy import copy, deepcopy
from pprint import pprint
from random import choice, randint
from secrets import token_bytes

import didkit
from config import providers
from dotenv import dotenv_values
from web3 import Web3

w3 = Web3()


env_config = dotenv_values(".env")


JWK = env_config["JWK"]
mnemonic = env_config["MNEMONIC"]


print(sys.argv)

# shard_idx = int(sys.argv[1])
# num_shards = int(sys.argv[2])

with open("generated_accounts.json") as f:
    addresses = json.load(f)

num_total_accounts = len(addresses)
print("Num addresses:", num_total_accounts)


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
    for i in range(100):
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

#
#  //{address}/vcs.json
#  /{address}/vcs.json
#
#
