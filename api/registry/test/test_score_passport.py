from unittest.mock import patch

from account.models import Account, Community
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from registry.exceptions import NoPassportException
from registry.models import Passport, Score
from registry.tasks import score_passport
from web3 import Web3

my_mnemonic = settings.TEST_MNEMONIC
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()


class TestScorePassportTestCase(TransactionTestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create_user(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        account_2 = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        self.account = account
        self.account_2 = account_2

        self.user_account = Account.objects.create(
            user=self.user, address=account.address
        )

        # Mock the default weights for new communities that are created
        with patch(
            "scorer_weighted.models.settings.GITCOIN_PASSPORT_WEIGHTS",
            {
                "Google": 1,
                "Ens": 1,
            },
        ):
            self.community = Community.objects.create(
                name="My Community",
                description="My Community description",
                account=self.user_account,
            )

        self.client = Client()

    def test_no_passport(self):

        with patch("registry.tasks.get_passport", return_value=None):
            score_passport(self.community.id, self.account.address)

            passport = Passport.objects.get(
                address=self.account.address, community_id=self.community.id
            )
            self.assertEqual(passport.passport, None)

            score = Score.objects.get(passport=passport)
            self.assertEqual(score.score, None)
            self.assertEqual(score.last_score_timestamp, None)
            self.assertEqual(score.evidence, None)
            self.assertEqual(score.status, Score.Status.ERROR)
            self.assertEqual(score.error, "No Passport found for this address.")
