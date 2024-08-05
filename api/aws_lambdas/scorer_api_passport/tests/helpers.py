class MockContext:
    aws_request_id = "sample_request_id"


address = "0x0de6eC538957216Fed96803c63902C3Aa5f39640"

headers = {"Authorization": "bla"}

good_stamp = {
    "provider": "Google",
    "stamp": {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "id": "did:pkh:eip155:1:" + address,
            "provider": "Google",
            "hash": "v0.0.0:6JvcAp7Ij5c1WJm1T/9Kt/GMVM4uWdpwQ8zSY3LLM9k=",
            "@context": [
                {
                    "hash": "https://schema.org/Text",
                    "provider": "https://schema.org/Text",
                }
            ],
        },
        "issuer": "did:key:z6Mkwg65BN2xg6qicufGYR9Sxn3NWwfBxRFrKVEPrZXVAx3z",
        "issuanceDate": "2023-10-18T15:45:53.705Z",
        "proof": {
            "type": "Ed25519Signature2018",
            "proofPurpose": "assertionMethod",
            "verificationMethod": "did:key:z6Mkwg65BN2xg6qicufGYR9Sxn3NWwfBxRFrKVEPrZXVAx3z#z6Mkwg65BN2xg6qicufGYR9Sxn3NWwfBxRFrKVEPrZXVAx3z",
            "created": "2023-10-18T15:45:53.706Z",
            "proofValue": "iamasignature",
        },
        "expirationDate": "2024-01-16T16:45:53.705Z",
    },
}
