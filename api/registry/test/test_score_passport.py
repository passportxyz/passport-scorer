import copy
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import call, patch

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase
from web3 import Web3

from account.models import Account, AccountAPIKey, Community
from registry.api.schema import StatusEnum
from registry.api.v1 import SubmitPassportPayload, a_submit_passport, get_score
from registry.models import Event, HashScorerLink, Passport, Score, Stamp
from registry.tasks import score_passport
from scorer_weighted.models import Scorer, WeightedScorer

User = get_user_model()
my_mnemonic = settings.TEST_MNEMONIC
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

now = datetime.now(timezone.utc)
expiration_dates = [
    now + timedelta(days=2),
    now + timedelta(days=1),
    now + timedelta(days=3),
]

mocked_weights = {
    "Ens": 1.0,
    "Google": 2.0,
    "Gitcoin": 3.0,
}

trusted_issuer = [
    issuer for issuer in settings.TRUSTED_IAM_ISSUERS if issuer.startswith("did:ethr:")
][0]

mock_passport_data = {
    "stamps": [
        {
            "provider": "Ens",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": trusted_issuer,
                    "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
                    "provider": "Ens",
                },
                "issuer": trusted_issuer,
                "issuanceDate": (expiration_dates[0] - timedelta(days=30)).isoformat(),
                "expirationDate": expiration_dates[0].isoformat(),
            },
        },
        {
            "provider": "Google",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": trusted_issuer,
                    "hash": "0x88888",
                    "provider": "Google",
                },
                "issuer": trusted_issuer,
                "issuanceDate": (expiration_dates[1] - timedelta(days=30)).isoformat(),
                "expirationDate": expiration_dates[1].isoformat(),
            },
        },
        {
            "provider": "Gitcoin",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": trusted_issuer,
                    "hash": "0x45678",
                    "provider": "Gitcoin",
                },
                "issuer": trusted_issuer,
                "issuanceDate": (expiration_dates[2] - timedelta(days=30)).isoformat(),
                "expirationDate": expiration_dates[2].isoformat(),
            },
        },
    ]
}
mock_min_expiration_date = min(
    *[s["credential"]["expirationDate"] for s in mock_passport_data["stamps"]]
)


def mock_validate(*args, **kwargs):
    return []


class TestScorePassportTestCase(TransactionTestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        account_2 = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/1"
        )
        account_3 = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/2"
        )
        self.account = account
        self.account_2 = account_2
        self.account_3 = account_3

        self.user_account = Account.objects.create(
            user=self.user, address=account.address
        )

        (api_key_instance, _) = AccountAPIKey.objects.create_key(
            account=self.user_account, name="Token for user 1"
        )
        self.api_key = api_key_instance

        self.community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=self.user_account,
            scorer=WeightedScorer.objects.create(
                type=Scorer.Type.WEIGHTED,
                weights=mocked_weights,
            ),
        )

        self.client = Client()

    def test_no_passport(self):
        with patch("registry.atasks.aget_passport", return_value=None):
            score_passport(self.community.pk, self.account.address)

            passport = Passport.objects.get(
                address=self.account.address, community_id=self.community.pk
            )
            self.assertEqual(passport.stamps.all().count(), 0)

            score = Score.objects.get(passport=passport)
            self.assertEqual(score.score, None)
            self.assertEqual(score.last_score_timestamp, None)
            self.assertEqual(score.evidence, None)
            self.assertEqual(score.status, Score.Status.ERROR)
            self.assertEqual(score.error, "No Passport found for this address.")
            self.assertEqual(score.expiration_date, None)

    def test_score_checksummed_address(self):
        address = self.account.address
        assert re.search("[A-Z]", address) is not None

        self._score_address(address)

    def test_score_nonchecksummed_address(self):
        address = self.account.address.lower()
        assert re.search("[A-Z]", address) is None

        self._score_address(address)

    def _score_address(self, address):
        class MockRequest:
            def __init__(self):
                pass

        mock_request = MockRequest()
        mock_request.auth = self.user_account
        mock_request.api_key = self.api_key
        mock_request.path = "/passport/"
        mock_request.GET = {}
        mock_request.headers = {}

        with patch("registry.api.v1.ascore_passport", return_value=None):
            async_to_sync(a_submit_passport)(
                mock_request,
                SubmitPassportPayload(
                    address=address,
                    community=self.community.pk,
                ),
            )

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport(self.community.pk, address)

        Passport.objects.get(address=address, community_id=self.community.pk)

        score = get_score(mock_request, address, self.community.pk)
        assert score.last_score_timestamp is not None
        score_dict = score.model_dump()
        assert score.model_dump() == {
            # attributes set automatically
            "last_score_timestamp": score_dict["last_score_timestamp"],
            # attributes we expect to have a specific value
            "address": self.account.address.lower(),
            "evidence": None,
            "error": None,
            "score": Decimal("6.000000000"),
            "status": StatusEnum.done,
            "stamp_scores": mocked_weights,
            "expiration_date": mock_min_expiration_date,
        }

    def test_cleaning_stale_stamps(self):
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        Stamp.objects.update_or_create(
            passport=passport,
            defaults={"provider": "Gitcoin", "credential": "{}"},
        )

        assert Stamp.objects.filter(passport=passport).count() == 1

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport(self.community.pk, self.account.address)

                my_stamps = Stamp.objects.filter(passport=passport)
                assert len(my_stamps) == 3

                gitcoin_stamps = my_stamps.filter(provider="Gitcoin")
                assert len(gitcoin_stamps) == 1

    def test_deduplication_of_scoring_tasks(self):
        """
        Test that when multiple tasks are scheduled for the same Passport, only one of them will execute the scoring calculation, and it will also reset the requires_calculation to False
        """
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        Stamp.objects.update_or_create(
            passport=passport,
            defaults={"provider": "Gitcoin", "credential": "{}"},
        )

        assert Stamp.objects.filter(passport=passport).count() == 1

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                with patch("registry.tasks.log.info") as mock_log:
                    # Call score_passport_passport twice, but only one of them should actually execute the scoring calculation
                    score_passport(self.community.pk, self.account.address)
                    score_passport(self.community.pk, self.account.address)

                    expected_call = call(
                        "Passport no passport found for address='%s', community_id='%s' that has requires_calculation=True or None",
                        self.account.address,
                        self.community.pk,
                    )
                    assert mock_log.call_args_list.count(expected_call) == 1
                    assert (
                        Passport.objects.get(pk=passport.pk).requires_calculation
                        is False
                    )

    def test_lifo_duplicate_stamp_scoring(self):
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        passport_for_already_existing_stamp, _ = Passport.objects.update_or_create(
            address=self.account_2.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        mocked_duplicate_stamps = {"stamps": mock_passport_data["stamps"][:1]}
        mocked_non_duplicate_stamps = {"stamps": mock_passport_data["stamps"][1:]}

        for stamp in mocked_duplicate_stamps["stamps"]:
            Stamp.objects.create(
                passport=passport_for_already_existing_stamp,
                provider=stamp["provider"],
                credential=json.dumps(stamp["credential"]),
            )

            HashScorerLink.objects.create(
                hash=stamp["credential"]["credentialSubject"]["hash"],
                address=passport_for_already_existing_stamp.address,
                community=passport_for_already_existing_stamp.community,
                expires_at=stamp["credential"]["expirationDate"],
            )

        with patch("registry.atasks.validate_credential", side_effect=mock_validate):
            # Score original passport
            with patch(
                "registry.atasks.aget_passport",
                return_value=mock_passport_data,
            ):
                score_passport(self.community.pk, passport.address)

            original_stamps = Stamp.objects.filter(passport=passport)
            assert len(original_stamps) == len(mocked_non_duplicate_stamps["stamps"])

            assert Event.objects.filter(
                action=Event.Action.LIFO_DEDUPLICATION
            ).count() == len(mocked_duplicate_stamps["stamps"])

            assert (Score.objects.get(passport=passport).score) == Decimal(
                sum(
                    mocked_weights[s["credential"]["credentialSubject"]["provider"]]
                    for s in mocked_non_duplicate_stamps["stamps"]
                )
            )

            # All the stamps we worked with should be registered in HashScorerLink by now
            assert HashScorerLink.objects.all().count() == len(
                mock_passport_data["stamps"]
            )

    def test_score_events(self):
        count = Event.objects.filter(action=Event.Action.SCORE_UPDATE).count()

        Score.objects.create(
            passport=Passport.objects.create(
                address=self.account.address, community_id=self.community.pk
            ),
            score=1,
            status="DONE",
        )

        assert (
            Event.objects.filter(action=Event.Action.SCORE_UPDATE).count() == count + 1
        )

    def test_score_expiration_time(self):
        """
        Test that the score expiration time is correctly calculated and stored
        """
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        expected_score_expiration = min(expiration_dates)

        for idx, credential in enumerate(mock_passport_data["stamps"]):
            Stamp.objects.create(
                passport=passport,
                provider=credential["provider"],
                credential=credential,
            )

        assert Stamp.objects.filter(passport=passport).count() == len(expiration_dates)

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport(self.community.pk, self.account.address)

                score = Score.objects.get(passport=passport)

                assert score.expiration_date == expected_score_expiration

    def test_score_expiration_time_when_all_stamps_expired(self):
        """
        Test that the score expiration time is set to None when recalculating the score when all stamps are expired
        """
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        expected_score_expiration = min(expiration_dates)

        #############################################################################################
        # Step 1: calculate the score as usual, with all stamps valid
        #############################################################################################
        for idx, credential in enumerate(mock_passport_data["stamps"]):
            Stamp.objects.create(
                passport=passport,
                provider=credential["provider"],
                credential=credential,
            )

        assert Stamp.objects.filter(passport=passport).count() == len(expiration_dates)

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport(self.community.pk, self.account.address)

                score = Score.objects.get(passport=passport)

                assert score.expiration_date == expected_score_expiration

        #############################################################################################
        # Step 2: calculate the score as usual, with a passport where all stamps are expired
        #############################################################################################
        passport.requires_calculation = True
        passport.save()

        mock_passport_data_expired = copy.deepcopy(mock_passport_data)
        for stamp in mock_passport_data_expired["stamps"]:
            stamp["credential"]["expirationDate"] = (
                now - timedelta(days=1)
            ).isoformat()

        with patch(
            "registry.atasks.aget_passport", return_value=mock_passport_data_expired
        ):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport(self.community.pk, self.account.address)

                score = Score.objects.get(passport=passport)

                assert score.score == 0
                assert score.expiration_date is None
