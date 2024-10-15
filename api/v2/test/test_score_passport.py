import copy
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import call, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase
from web3 import Web3

from account.models import Account, AccountAPIKey, Community
from registry.api.v1 import SubmitPassportPayload, a_submit_passport, get_score
from registry.models import Event, HashScorerLink, Passport, Score, Stamp
from registry.tasks import score_passport_passport, score_registry_passport

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

mock_passport_data = {
    "stamps": [
        {
            "provider": "Ens",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": settings.TRUSTED_IAM_ISSUERS[0],
                    "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
                    "provider": "Ens",
                },
                "issuer": settings.TRUSTED_IAM_ISSUERS[0],
                "issuanceDate": (expiration_dates[0] - timedelta(days=30)).isoformat(),
                "expirationDate": expiration_dates[0].isoformat(),
            },
        },
        {
            "provider": "Google",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": settings.TRUSTED_IAM_ISSUERS[0],
                    "hash": "0x88888",
                    "provider": "Google",
                },
                "issuer": settings.TRUSTED_IAM_ISSUERS[0],
                "issuanceDate": (expiration_dates[1] - timedelta(days=30)).isoformat(),
                "expirationDate": expiration_dates[1].isoformat(),
            },
        },
        {
            "provider": "Gitcoin",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": settings.TRUSTED_IAM_ISSUERS[0],
                    "hash": "0x45678",
                    "provider": "Gitcoin",
                },
                "issuer": settings.TRUSTED_IAM_ISSUERS[0],
                "issuanceDate": (expiration_dates[2] - timedelta(days=30)).isoformat(),
                "expirationDate": expiration_dates[2].isoformat(),
            },
        },
    ]
}


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

        AccountAPIKey.objects.create_key(
            account=self.user_account, name="Token for user 1"
        )

        self.community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=self.user_account,
        )

        self.client = Client()

    def test_no_passport(self):
        with patch("registry.atasks.aget_passport", return_value=None):
            score_passport_passport(self.community.pk, self.account.address)

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

    async def _score_address(self, address):
        class MockRequest:
            def __init__(self, account):
                self.auth = account
                self.api_key = account.api_keys.all()[0]

        mock_request = MockRequest(self.user_account)

        with patch("registry.api.v1.score_passport_passport.delay", return_value=None):
            await a_submit_passport(
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
                score_passport_passport(self.community.pk, address)

        Passport.objects.get(address=address, community_id=self.community.pk)

        score = get_score(mock_request, address, self.community.pk)
        assert Decimal(score.score) == Decimal("3")
        assert score.status == "DONE"

    def test_cleaning_stale_stamps(self):
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        Stamp.objects.update_or_create(
            hash="0x1234",
            passport=passport,
            defaults={"provider": "Gitcoin", "credential": "{}"},
        )

        assert Stamp.objects.filter(passport=passport).count() == 1

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport_passport(self.community.pk, self.account.address)

                my_stamps = Stamp.objects.filter(passport=passport)
                assert len(my_stamps) == 3

                gitcoin_stamps = my_stamps.filter(provider="Gitcoin")
                assert len(gitcoin_stamps) == 1
                assert gitcoin_stamps[0].hash == "0x45678"

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
            hash="0x1234",
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
                    score_passport_passport(self.community.pk, self.account.address)
                    score_passport_passport(self.community.pk, self.account.address)

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

        passport_with_duplicates, _ = Passport.objects.update_or_create(
            address=self.account_3.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        already_existing_stamp = {
            "provider": "POAP",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": settings.TRUSTED_IAM_ISSUERS[0],
                    "hash": "0x1111",
                    "provider": "Gitcoin",
                },
                "issuer": settings.TRUSTED_IAM_ISSUERS[0],
                "issuanceDate": "2023-02-06T23:22:58.848Z",
                "expirationDate": "2099-02-06T23:22:58.848Z",
            },
        }

        Stamp.objects.update_or_create(
            hash=already_existing_stamp["credential"]["credentialSubject"]["hash"],
            passport=passport_for_already_existing_stamp,
            defaults={
                "provider": already_existing_stamp["provider"],
                "credential": json.dumps(already_existing_stamp["credential"]),
            },
        )

        HashScorerLink.objects.create(
            hash=already_existing_stamp["credential"]["credentialSubject"]["hash"],
            address=passport_for_already_existing_stamp.address,
            community=passport_for_already_existing_stamp.community,
            expires_at=already_existing_stamp["credential"]["expirationDate"],
        )

        mock_passport_data_with_duplicates = {
            "stamps": [
                mock_passport_data["stamps"][0],
                already_existing_stamp,
                {
                    "provider": "Google",
                    "credential": {
                        "type": ["VerifiableCredential"],
                        "credentialSubject": {
                            "id": settings.TRUSTED_IAM_ISSUERS[0],
                            "hash": "0x12121",
                            "provider": "Google",
                        },
                        "issuer": settings.TRUSTED_IAM_ISSUERS[0],
                        "issuanceDate": "2023-02-06T23:22:58.848Z",
                        "expirationDate": "2099-02-06T23:22:58.848Z",
                    },
                },
            ]
        }

        with patch("registry.atasks.validate_credential", side_effect=mock_validate):
            # Score original passport
            with patch(
                "registry.atasks.aget_passport", return_value=mock_passport_data
            ):
                score_registry_passport(self.community.pk, passport.address)

            assert (
                Event.objects.filter(action=Event.Action.LIFO_DEDUPLICATION).count()
                == 0
            )

            # Score passport with duplicates (one duplicate from original passport,
            # one duplicate from already existing stamp)
            with patch(
                "registry.atasks.aget_passport",
                return_value=mock_passport_data_with_duplicates,
            ):
                score_registry_passport(
                    self.community.pk, passport_with_duplicates.address
                )

            original_stamps = Stamp.objects.filter(passport=passport)
            assert len(original_stamps) == 3

            assert (Score.objects.get(passport=passport).score) == Decimal(
                "0.933000000"
            )

            assert (
                Event.objects.filter(action=Event.Action.LIFO_DEDUPLICATION).count()
                == 2
            )

            deduplicated_stamps = Stamp.objects.filter(
                passport=passport_with_duplicates
            )
            assert len(deduplicated_stamps) == 1

            assert (
                Score.objects.get(passport=passport_with_duplicates).score
            ) == Decimal("0.525000000")

            passport.requires_calculation = True
            passport.save()
            # Re-score original passport, just to make sure it doesn't change
            with patch(
                "registry.atasks.aget_passport", return_value=mock_passport_data
            ):
                score_registry_passport(self.community.pk, passport.address)

            assert (Score.objects.get(passport=passport).score) == Decimal(
                "0.933000000"
            )
            assert (
                Event.objects.filter(action=Event.Action.LIFO_DEDUPLICATION).count()
                == 2
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
            Stamp.objects.update_or_create(
                hash=f"0x1234{idx}",
                passport=passport,
                defaults={
                    "provider": credential["provider"],
                    "credential": credential,
                },
            )

        assert Stamp.objects.filter(passport=passport).count() == len(expiration_dates)

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport_passport(self.community.pk, self.account.address)

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
            Stamp.objects.update_or_create(
                hash=f"0x1234{idx}",
                passport=passport,
                defaults={
                    "provider": credential["provider"],
                    "credential": credential,
                },
            )

        assert Stamp.objects.filter(passport=passport).count() == len(expiration_dates)

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport_passport(self.community.pk, self.account.address)

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
                score_passport_passport(self.community.pk, self.account.address)

                score = Score.objects.get(passport=passport)

                assert score.score == 0
                assert score.expiration_date is None
