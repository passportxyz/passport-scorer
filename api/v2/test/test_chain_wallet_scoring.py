import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from django.utils import timezone as django_timezone

from account.linkage import WalletCluster, WalletIdentity
from account.models import Account, AccountAPIKey, Community
from aws_lambdas.scorer_api_passport.tests.helpers import MockContext
from ceramic_cache.models import ChainWalletStamp, Revocation
from registry.models import ChainWalletScore, HashScorerLink, Passport
from scorer_weighted.models import BinaryWeightedScorer, Scorer
from v2.aws_lambdas.stamp_score_GET import _handler as stamp_score_lambda

ADDRESS = "0x" + "a" * 40
ISSUER = "did:key:scoped-wallet-test"
CANONICAL = WalletIdentity("0x" + "b" * 40)


@override_settings(TRUSTED_IAM_ISSUERS=[ISSUER])
class ChainWalletScoringTest(TransactionTestCase):
    def setUp(self):
        account = Account.objects.create(
            user=User.objects.create_user(username="chain-wallet"),
            address=ADDRESS,
        )
        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY,
            weights={"Google": "10", "Github": "5", "Discord": "2"},
            threshold=Decimal("10"),
        )
        self.community = Community.objects.create(
            name="Chain wallet", account=account, scorer=scorer
        )
        _, self.key = AccountAPIKey.objects.create_key(
            account=account, name="Wallet backend", linked_wallet_breakdown=True
        )
        _, self.other_key = AccountAPIKey.objects.create_key(
            account=account, name="Linkage hidden"
        )

    def credential(
        self,
        chain,
        provider,
        nullifier,
        *,
        revoked=False,
    ):
        credential = {
            "issuer": ISSUER,
            "expirationDate": (
                datetime.now(timezone.utc) + timedelta(days=2)
            ).isoformat(),
            "credentialSubject": {
                "id": f"did:pkh:eip155:{chain}:{ADDRESS}",
                "provider": provider,
                "nullifiers": [nullifier],
            },
        }
        stamp = ChainWalletStamp.objects.create(
            chain_id=chain,
            address=ADDRESS,
            provider=provider,
            stamp=credential,
            proof_value=f"{chain}:{provider}:{nullifier}",
        )
        if revoked:
            Revocation.objects.create(
                chain_wallet_stamp=stamp, proof_value=stamp.proof_value
            )
        return stamp

    def cluster_for(self, wallet):
        return WalletCluster(CANONICAL, (CANONICAL, wallet))

    def score_canonical(self, key):
        return self.client.get(
            f"/v2/stamps/{self.community.pk}/score/{CANONICAL.address}",
            HTTP_X_API_KEY=key,
        )

    def score(self, chain, key=None):
        return self.client.get(
            f"/v2/stamps/{self.community.pk}/score/eip155/{chain}/{ADDRESS.upper().replace('0X', '0x')}",
            HTTP_X_API_KEY=key or self.key,
        )

    def test_credentials_and_score_rows_are_isolated_by_chain(self):
        base_google = self.credential(8453, "Google", "base-google")
        self.credential(8453, "Github", "shared")
        self.credential(1, "Google", "eth-google")
        self.credential(1, "Discord", "shared")
        self.credential(8453, "Twitter", "revoked", revoked=True)
        ChainWalletStamp.objects.filter(pk=base_google.pk).update(
            updated_at=django_timezone.now() - timedelta(days=1)
        )

        HashScorerLink.objects.create(
            community=self.community,
            address=ADDRESS,
            hash="eth-google",
            expires_at=django_timezone.now() + timedelta(days=1),
        )

        with (
            patch(
                "v2.api.api_stamps.get_wallet_cluster",
                new=AsyncMock(side_effect=self.cluster_for),
            ) as linked,
            patch(
                "registry.atasks.validate_credential", new=AsyncMock(return_value=[])
            ) as validate,
        ):
            base = self.score(8453)
            eth = self.score(1)
        self.assertEqual((base.status_code, eth.status_code), (200, 200))
        self.assertEqual(base.json()["linked_score"]["score"], "15.00000")
        self.assertEqual(eth.json()["linked_score"]["score"], "10.00000")
        self.assertTrue(
            eth.json()["linked_score"]["wallet_stamps"][f"eip155:1:{ADDRESS}"][
                "Discord"
            ]["dedup"]
        )
        self.assertEqual(
            linked.await_args_list[0].args, (WalletIdentity(ADDRESS, 8453),)
        )
        calls = {
            (args[0], args[1]["credentialSubject"]["nullifiers"][0])
            for args, _ in validate.await_args_list
        }
        self.assertIn((f"did:pkh:eip155:8453:{ADDRESS}", "base-google"), calls)
        self.assertIn((f"did:pkh:eip155:1:{ADDRESS}", "eth-google"), calls)
        self.assertNotIn((f"did:pkh:eip155:8453:{ADDRESS}", "revoked"), calls)
        self.assertEqual(
            list(
                ChainWalletScore.objects.order_by("chain_id").values_list(
                    "chain_id", "address"
                )
            ),
            [(1, ADDRESS), (8453, ADDRESS)],
        )
        self.assertEqual(HashScorerLink.objects.get(hash="shared").chain_id, 8453)
        self.assertFalse(Passport.objects.filter(address=ADDRESS).exists())

    def test_requires_privileged_key_and_active_link(self):
        with patch(
            "v2.api.api_stamps.get_wallet_cluster",
            new=AsyncMock(return_value=None),
        ) as linked:
            self.assertEqual(self.score(8453, key=self.other_key).status_code, 403)
            linked.assert_not_awaited()
            self.assertEqual(self.score(8453).status_code, 404)
        self.assertFalse(ChainWalletScore.objects.exists())

    def test_lambda_routes_to_the_chain_wallet_scorer(self):
        with patch(
            "v2.api.api_stamps.get_wallet_cluster",
            new=AsyncMock(side_effect=self.cluster_for),
        ) as linked:
            response = stamp_score_lambda(
                {
                    "httpMethod": "GET",
                    "path": f"/v2/stamps/{self.community.pk}/score/eip155/8453/{ADDRESS}",
                    "headers": {"x-api-key": self.key},
                    "isBase64Encoded": False,
                },
                MockContext(),
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["chain_id"], 8453)
        linked.assert_awaited_once_with(WalletIdentity(ADDRESS, 8453))
        self.assertTrue(
            ChainWalletScore.objects.filter(chain_id=8453, address=ADDRESS).exists()
        )

    def test_typed_cluster_drops_unlinked_contribution_and_hides_member_identities(
        self,
    ):
        self.credential(8453, "Github", "base")
        self.credential(1, "Discord", "eth")
        cluster = WalletCluster(
            CANONICAL,
            (
                CANONICAL,
                WalletIdentity(ADDRESS, 1),
                WalletIdentity(ADDRESS, 8453),
            ),
        )
        with (
            patch(
                "v2.api.api_stamps.get_wallet_cluster",
                new=AsyncMock(side_effect=[cluster, cluster, None, None]),
            ),
            patch(
                "registry.atasks.validate_credential", new=AsyncMock(return_value=[])
            ),
        ):
            linked = self.score_canonical(self.key).json()
            hidden = self.score_canonical(self.other_key).json()
            unlinked = self.score_canonical(self.key).json()
            self.assertEqual(self.score(8453).status_code, 404)

        self.assertEqual(linked["score"], "7.00000")
        self.assertEqual(
            set(linked["linked_score"]["wallet_stamps"]),
            {f"eip155:1:{ADDRESS}", f"eip155:8453:{ADDRESS}"},
        )
        self.assertEqual(linked["stamps"]["Github"]["source_wallet_chain_id"], 8453)
        self.assertEqual(linked["stamps"]["Discord"]["source_wallet_chain_id"], 1)
        self.assertEqual(hidden["score"], "7.00000")
        self.assertIsNone(hidden["linked_score"])
        self.assertNotIn("source_wallet_chain_id", hidden["stamps"]["Github"])
        self.assertEqual(unlinked["score"], "0.00000")
