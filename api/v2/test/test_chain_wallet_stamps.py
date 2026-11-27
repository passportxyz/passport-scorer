from datetime import timedelta
from unittest.mock import AsyncMock, patch

import jwt
from asgiref.sync import async_to_sync
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.test import TransactionTestCase, override_settings

from account.models import Nonce
from ceramic_cache.api.v1 import CHAIN_WALLET_STATEMENT, generate_siwe_access_token
from ceramic_cache.models import CeramicCache, ChainWalletStamp, Revocation
from reader.passport_reader import aget_passport
from registry.utils import get_utc_time

ADDRESS = "0x" + "a" * 40
ISSUER = "did:key:trusted-test-issuer"


class ChainWalletStampsTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = (
            key.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        cls.enterClassContext(
            override_settings(
                SIWE_JWT_PRIVATE_KEY=private,
                SIWE_JWT_PUBLIC_KEY=public,
                TRUSTED_IAM_ISSUERS=[ISSUER],
                SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE=["app.passport.xyz"],
            )
        )
        cls.enterClassContext(
            patch.dict("os.environ", {"CHAIN_WALLET_SCORING_ENABLED": "true"})
        )

    def did(self, chain_id):
        return f"did:pkh:eip155:{chain_id}:{ADDRESS}"

    def update(self, chain_id, credential=None, *, scoped=True):
        token = generate_siwe_access_token(self.did(chain_id), chain_wallet=scoped)
        return self.client.patch(
            "/v2/wallet-stamps",
            data=[{"provider": "Google", "stamp": credential}],
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def credential(self, chain_id):
        return {
            "issuer": ISSUER,
            "credentialSubject": {"id": self.did(chain_id), "provider": "Google"},
            "proof": {"proofValue": f"proof-{chain_id}"},
        }

    def cached_stamps(self, chain_id):
        token = generate_siwe_access_token(self.did(chain_id), chain_wallet=True)
        response = self.client.get(
            "/v2/wallet-stamps", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        return [row["stamp"] for row in response.json()["stamps"]]

    def test_mainnet_cache_and_scoring_preserve_existing_wallet_stamps(self):
        credential = self.credential(1)
        legacy = CeramicCache.objects.create(
            address=ADDRESS, provider="Google", stamp=credential, proof_value="proof-1"
        )
        self.assertEqual(self.cached_stamps(1), [credential])
        self.assertEqual(self.cached_stamps(8453), [])
        scored = async_to_sync(aget_passport)(ADDRESS, chain_id=1)
        self.assertEqual(
            scored["stamps"], [{"provider": "Google", "credential": credential}]
        )

        other = CeramicCache.objects.create(
            address=ADDRESS,
            provider="Google",
            stamp=self.credential(8453),
            type=CeramicCache.StampType.V2,
            proof_value="proof-8453",
        )
        self.assertEqual(self.update(1).json()["stamps"], [])
        legacy.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(legacy.deleted_at)
        self.assertIsNone(other.deleted_at)
        CeramicCache.objects.create(
            address=ADDRESS, provider="Google", stamp=credential, proof_value="proof-1"
        )
        self.assertEqual(self.cached_stamps(1), [])
        self.assertEqual(
            async_to_sync(aget_passport)(ADDRESS, chain_id=1)["stamps"], []
        )

    def test_revoked_or_superseded_legacy_stamps_do_not_return(self):
        credential = self.credential(1)
        legacy = CeramicCache.objects.create(
            address=ADDRESS, provider="Google", stamp=credential, proof_value="proof-1"
        )
        Revocation.objects.create(ceramic_cache=legacy, proof_value="proof-1")
        self.assertEqual(self.cached_stamps(1), [])

        # A later legacy row must not take over after a scoped row is deleted.
        CeramicCache.objects.filter(pk=legacy.pk).update(
            stamp={**credential, "proof": {"proofValue": "other-legacy-proof"}},
            proof_value="other-legacy-proof",
        )
        Revocation.objects.filter(ceramic_cache=legacy).delete()
        ChainWalletStamp.objects.create(
            address=ADDRESS,
            chain_id=1,
            provider="Google",
            stamp=credential,
            proof_value="scoped-proof",
            deleted_at=get_utc_time(),
        )
        self.assertEqual(self.cached_stamps(1), [])
        self.assertEqual(
            async_to_sync(aget_passport)(ADDRESS, chain_id=1)["stamps"], []
        )

    def test_cache_replacement_and_deletion_preserve_other_chain(self):
        with patch(
            "v2.api.chain_wallet_stamps.validate_credential",
            new=AsyncMock(return_value=[]),
        ):
            self.assertEqual(self.update(1, self.credential(1)).status_code, 200)
            self.assertEqual(self.update(8453, self.credential(8453)).status_code, 200)
            self.assertEqual(self.update(1, self.credential(8453)).status_code, 400)
            self.assertEqual(self.update(1, scoped=False).status_code, 401)
            self.assertEqual(self.update(1).json()["stamps"], [])
        self.assertEqual(
            list(
                ChainWalletStamp.objects.filter(deleted_at__isnull=True).values_list(
                    "chain_id", flat=True
                )
            ),
            [8453],
        )

    def test_mainnet_scoped_token_cannot_use_the_legacy_cache(self):
        token = generate_siwe_access_token(self.did(1), chain_wallet=True)
        response = self.client.get(
            f"/ceramic-cache/score/{ADDRESS}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 401)

    def test_revoked_proof_cannot_be_cached_again(self):
        with patch(
            "v2.api.chain_wallet_stamps.validate_credential",
            new=AsyncMock(return_value=[]),
        ):
            self.assertEqual(self.update(8453, self.credential(8453)).status_code, 200)
            stamp = ChainWalletStamp.objects.get(chain_id=8453)
            Revocation.objects.create(
                proof_value=stamp.proof_value, chain_wallet_stamp=stamp
            )
            self.assertEqual(self.update(8453, self.credential(8453)).status_code, 400)

    def test_deployed_wallet_siwe_issues_chain_subject_and_spends_nonce_once(self):
        nonce = Nonce.create_nonce(ttl=300)
        now = get_utc_time()
        payload = {
            "deployed_wallet": True,
            "signature": "0x1234",
            "message": {
                "domain": "app.passport.xyz",
                "uri": "https://app.passport.xyz",
                "statement": CHAIN_WALLET_STATEMENT,
                "version": "1",
                "chainId": 8453,
                "address": ADDRESS,
                "nonce": nonce.nonce,
                "issuedAt": now.isoformat(),
                "expirationTime": (now + timedelta(minutes=5)).isoformat(),
            },
        }
        with patch(
            "ceramic_cache.api.v1.verify_deployed_wallet_signature", return_value=True
        ) as verify:
            response = self.client.post(
                "/ceramic-cache/authenticate/v2",
                payload,
                content_type="application/json",
            )
            replay = self.client.post(
                "/ceramic-cache/authenticate/v2",
                payload,
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotEqual(replay.status_code, 200)
        self.assertEqual(verify.call_args.args[0], 8453)
        claims = jwt.decode(
            response.json()["access"],
            settings.SIWE_JWT_PUBLIC_KEY,
            algorithms=["RS256"],
        )
        self.assertEqual(claims["did"], self.did(8453))
        self.assertTrue(claims["chain_wallet"])
