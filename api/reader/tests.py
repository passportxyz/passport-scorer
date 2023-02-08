from unittest.mock import patch

from datetime import datetime

import pytest
from ceramic_cache.models import CeramicCache

from .passport_reader import get_passport

# Location of a Ceramic node that we can read state from
CERAMIC_URL = "https://ceramic.passport-iam.gitcoin.co"


sample_stamps = [
    {
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
    },
    {
        "type": ["VerifiableCredential"],
        "proof": {
            "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..zuoM022TajcVdKlojUBD4Y3fAVhEkhWGj9MKALDIicKtLjzKIjcXH9WAx721X7yqvJupa3b3PJmQFKxmxB-ZDw",
            "type": "Ed25519Signature2018",
            "created": "2023-01-09T21:57:00.365Z",
            "proofPurpose": "assertionMethod",
            "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
        },
        "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "issuanceDate": "2023-01-09T21:57:00.365Z",
        "expirationDate": "2099-04-09T21:57:00.365Z",
        "credentialSubject": {
            "id": "did:pkh:eip155:1:0x434b56e01a8BdD9AB8aE5Ef1aCf86E3372A877c3",
            "hash": "v0.0.0:XHpQZtxC+LhSrEgG8PA4q0/Wb2U+rmvlcaICg2SeOW8=",
            "@context": [
                {
                    "hash": "https://schema.org/Text",
                    "provider": "https://schema.org/Text",
                }
            ],
            "provider": "GitcoinContributorStatistics#numGrantsContributeToGte#1",
        },
    },
    {
        "type": ["VerifiableCredential"],
        "proof": {
            "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..QzVfUCyr6EZAA4ZxpS0XEnO5jn7OjepFo9H2qlpQaq3E5aozKexjVElhGwAqBuvzhZ6n4v8KQQk7rY33b4KhAg",
            "type": "Ed25519Signature2018",
            "created": "2023-01-09T21:57:01.476Z",
            "proofPurpose": "assertionMethod",
            "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
        },
        "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "issuanceDate": "2023-01-09T21:57:01.476Z",
        "expirationDate": "2099-04-09T21:57:01.476Z",
        "credentialSubject": {
            "id": "did:pkh:eip155:1:0x434b56e01a8BdD9AB8aE5Ef1aCf86E3372A877c3",
            "hash": "v0.0.0:SCGn9juQ2RYK1dvEAurvbAHHDfs+4/VOYdhqfAkGvBU=",
            "@context": [
                {
                    "hash": "https://schema.org/Text",
                    "provider": "https://schema.org/Text",
                }
            ],
            "provider": "GitcoinContributorStatistics#totalContributionAmountGte#10",
        },
    },
]


class TestGetStamps:
    @pytest.mark.django_db
    def test_only_ceramic_stamps(self):
        """Make sure cached ceramic stamps are returned when no cached stamps exist in the DB"""

        address = "0x123test"

        with patch(
            "reader.passport_reader.get_stamps",
            return_value={
                "stamps": [
                    {
                        "provider": s["credentialSubject"]["provider"],
                        "credential": s,
                    }
                    for s in sample_stamps
                ]
            },
        ):
            passport = get_passport(
                address,
                stream_ids=[
                    "1",
                    "2",
                    "3",
                ],
            )

        stamps = passport["stamps"]

        assert len(sample_stamps) == len(stamps)
        for (index, sample_stamp) in enumerate(sample_stamps):
            assert (
                stamps[index]["credential"]["issuanceDate"]
                == sample_stamp["issuanceDate"]
            )

    @pytest.mark.django_db
    def test_only_cached_stamps(self):
        """Make sure cached stamps are returned when they exist in the DB and the ceramic stamps are ignored"""

        address = "0x123test"

        good_stamps = sample_stamps[:2]
        bad_stamp = sample_stamps[2]

        for stamp in good_stamps:
            CeramicCache.objects.create(
                address=address,
                provider=stamp["credentialSubject"]["provider"],
                stamp=stamp,
            )

        CeramicCache.objects.create(
            address=address,
            provider=bad_stamp["credentialSubject"]["provider"],
            stamp=bad_stamp,
            deleted_at=datetime.now(),
        )

        passport = get_passport(address)
        stamps = passport["stamps"]

        assert len(good_stamps) == len(stamps)

        for (index, sample_stamp) in enumerate(good_stamps):
            assert (
                stamps[index]["credential"]["issuanceDate"]
                == sample_stamp["issuanceDate"]
            )
