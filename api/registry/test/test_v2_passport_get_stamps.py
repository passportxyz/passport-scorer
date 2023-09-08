import pytest
from ceramic_cache.models import CeramicCache
from registry.test.test_passport_get_stamps import TestPassportGetStamps

pytestmark = pytest.mark.django_db


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


class TestPassportGetStampsV2(TestPassportGetStamps):
    """
    We just inherit all tests from v1 for v2, there is no change
    """

    base_url = "/registry/v2"
