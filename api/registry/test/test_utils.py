import copy
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from registry.utils import validate_credential

now = datetime.now(timezone.utc)
mock_did = "did:pkh:eip155:1:0x0636f974d29d947d4946b2091d769ec6d2d415de"

pytestmark = pytest.mark.django_db


mock_credential_with_hash = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "some_issuer",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "credentialSubject": {
        "id": mock_did,
        "hash": "v0.0.0:xG1Todke+0P1jphcnZhP/3UA5XUBMaEux4fHG86I20U=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Ens",
    },
}

mock_credential_with_nullifiers = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "some_issuer",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expirationDate": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "credentialSubject": {
        "id": mock_did,
        "nullifiers": ["v1:xG1Todke+0P1jphcnZhP/3UA5XUBMaEux4fHG86I20U="],
        "@context": [
            {
                "nullifiers": {
                    "@type": "https://schema.org/Text",
                    "@container": "@list",
                },
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Ens",
    },
}


@pytest.mark.parametrize(
    "credential",
    [mock_credential_with_hash, mock_credential_with_nullifiers],
)
class TestValidateCredential:
    @pytest.mark.asyncio
    async def test_validate_credential_success(
        self,
        mocker,
        credential,
    ):
        mocker.patch(
            "registry.utils.verify_credential",
            return_value=json.dumps({"errors": []}),
            new_callable=AsyncMock,
        )

        validation_errors = await validate_credential(mock_did, credential)

        assert validation_errors == []

    @pytest.mark.asyncio
    async def test_validate_credential_fails_if_hash_and_nullifiers_are_missing(
        self,
        mocker,
        credential,
    ):
        mocker.patch(
            "registry.utils.verify_credential",
            return_value=json.dumps({"errors": []}),
            new_callable=AsyncMock,
        )

        test_credential = copy.deepcopy(credential)

        if "hash" in test_credential["credentialSubject"]:
            del test_credential["credentialSubject"]["hash"]

        if "nullifiers" in test_credential["credentialSubject"]:
            del test_credential["credentialSubject"]["nullifiers"]

        validation_errors = await validate_credential(mock_did, test_credential)

        assert validation_errors == [
            "Missing attribute: hash and nullifiers (either one must be present)",
        ]
