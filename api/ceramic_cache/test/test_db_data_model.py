import pytest
from ceramic_cache.models import CeramicCache
from django.db.utils import IntegrityError

stamp = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..VTnsT-e3tjd1A6uEtVwd3eeEx8byIkZPS8IKVQiZboKKs6bAWgCsGzN_v3ccQw-tKxO3NgBAk4lKA7KQ290yCw",
        "type": "Ed25519Signature2018",
        "created": "2022-11-23T15:30:51.720Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": "2022-11-23T15:30:51.720Z",
    "expirationDate": "2099-02-21T15:30:51.720Z",
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x434b56e01a8BdD9AB8aE5Ef1aCf86E3372A877c3",
        "hash": "v0.0.0:zwvwqJiGNkDi2wZgimC4nUf5fdMJ8HIpg8pzXAViLSI=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Github",
    },
}


class TestGetStamps:
    @pytest.mark.django_db
    def test_no_duplicate_stamps(self):
        """Make sure that it is not possible to have duplicate stamps in the DB"""

        address = "0x123test"

        # Create the first stamp
        CeramicCache.objects.create(
            address=address,
            provider=stamp["credentialSubject"]["provider"],
            stamp=stamp,
        )

        with pytest.raises(IntegrityError) as exc_info:
            # Create the same stamp (same provider) again
            # We expect an exception to be thrown
            CeramicCache.objects.create(
                address=address,
                provider=stamp["credentialSubject"]["provider"],
                stamp=stamp,
            )
