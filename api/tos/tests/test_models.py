import pytest
from django.conf import settings
from eth_account.account import Account
from eth_account.messages import encode_defunct
from tos.models import Tos, TosAcceptanceProof
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db


class TestTosModelFunctions:
    def test_accept_tos(self):
        #  create the TOS object
        tos = Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING, active=True, content="Hello World !!!"
        )

        # get a message to sign
        message, nonce = Tos.get_message_with_nonce(Tos.TosType.IDENTITY_STAKING)

        # create an account and sign the messsage
        eth_account = Account.from_mnemonic(settings.TEST_MNEMONIC)

        encoded_message = encode_defunct(text=message)

        signature_obj = eth_account.sign_message(encoded_message)
        signature = signature_obj.signature.hex()

        # register the signature
        accept_ok = Tos.accept(
            Tos.TosType.IDENTITY_STAKING,
            nonce,
            signature,
        )

        assert accept_ok is True

        proof = TosAcceptanceProof.objects.get(
            tos=tos, address=eth_account.address.lower()
        )
        assert proof.nonce == nonce
        assert proof.signature == signature

    def test_has_any_accepted(self):
        tos = Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING, active=True, content="Hello World !!!"
        )
        assert tos.has_any_accepted() is False
        TosAcceptanceProof.objects.create(
            tos=tos, address="0x0", signature="0x0", nonce="12345"
        )
        assert tos.has_any_accepted() is True
