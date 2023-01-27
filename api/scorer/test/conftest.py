# pylint: disable=redefined-outer-name
import pytest
from account.models import Account, AccountAPIKey, Community
from django.contrib.auth.models import User
from ninja_jwt.schema import RefreshToken
from registry.models import Passport, Score
from scorer_weighted.models import BinaryWeightedScorer, Scorer
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db


@pytest.fixture
def scorer_user():
    user = User.objects.create_user(username="testuser-1", password="12345")
    print("scorer_user user", user)
    return user


@pytest.fixture
def access_token(scorer_user):
    refresh = RefreshToken.for_user(scorer_user)
    return refresh.access_token


@pytest.fixture
def scorer_community(scorer_account):
    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
    )
    return community


@pytest.fixture
def scorer_account(scorer_user):
    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    print("scorer_user", scorer_user)
    print("web3_account.address", web3_account.address)
    account = Account.objects.create(user=scorer_user, address=web3_account.address)
    return account


@pytest.fixture
def passport_holder_addresses():
    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    ret = []
    for i in range(5):
        web3_account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path=f"m/44'/60'/0'/0/{i + 1}"
        )
        ret.append(
            {
                "address": web3_account.address,
                "key": web3_account.key,
            }
        )

    return ret


@pytest.fixture
def scorer_api_key(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Token for user 1"
    )
    return secret


@pytest.fixture
def scorer_community_with_binary_scorer(mocker, scorer_account):
    mock_settings = {"Facebook": 1, "Google": 1, "Ens": 1}
    # Mock gitcoin scoring settings
    mocker.patch(
        "scorer_weighted.models.settings.GITCOIN_PASSPORT_WEIGHTS",
        mock_settings,
    )
    mocker.patch(
        "scorer_weighted.models.settings.GITCOIN_PASSPORT_THRESHOLD",
        75,
    )

    scorer = BinaryWeightedScorer.objects.create(type=Scorer.Type.WEIGHTED_BINARY)

    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
        scorer=scorer,
    )
    return community


@pytest.fixture
def scorer_passport(passport_holder_addresses, scorer_community):
    passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
        passport={"name": "John Doe"},
        community=scorer_community,
    )
    return passport


@pytest.fixture
def scorer_score(scorer_passport):
    stamp = Score.objects.create(
        passport=scorer_passport,
        score="0.650000000",
    )
    return stamp


@pytest.fixture
def scorer_community_with_gitcoin_default(mocker, scorer_account):
    mock_settings = {
        "Google": 1234,
        "Ens": 1000000,
    }
    # Mock gitcoin scoring settings
    mocker.patch(
        "scorer_weighted.models.settings.GITCOIN_PASSPORT_WEIGHTS",
        mock_settings,
    )

    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
    )
    return community


@pytest.fixture
def no_account_db_response():
    return {
        "detail": "No account found for the provided address.",
    }


@pytest.fixture
def api_key_object(scorer_account):
    (account_api_key, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="The Key"
    )
    return {
        "name": account_api_key,
        "api_key": secret,
    }


@pytest.fixture
def verifiable_credential():
    return """
        {
            "type": [
                "VerifiableCredential"
            ],
            "proof": {
                "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..zbjVKQieb8fI04ygmQRr8EUYoJ-NSjBiEtV-5zxVoPMeq2XPPE3lL_QUyVda7u5L9RtB1QvRQYtv5_3X0OnyAg",
                "type": "Ed25519Signature2018",
                "created": "2023-01-24T01:56:57.048Z",
                "proofPurpose": "assertionMethod",
                "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC"
            },
            "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
            "@context": [
                "https://www.w3.org/2018/credentials/v1"
            ],
            "issuanceDate": "2023-01-24T01:56:57.048Z",
            "expirationDate": "2023-04-24T01:56:57.048Z",
            "credentialSubject": {
                "id": "did:pkh:eip155:1:0xC79BFBF4e4824Cdb65C71f2eeb2D7f2db5dA1fB8",
                "hash": "v0.0.0:SxN5492/GCHVOL5I6IFVqR1M35N9MFMDFQlkOv64zUU=",
                "@context": [
                    {
                        "hash": "https://schema.org/Text",
                        "provider": "https://schema.org/Text"
                    }
                ],
                "provider": "Twitter"
            }
        }
    """


@pytest.fixture
def sample_provider():
    return "Twitter"


@pytest.fixture
def sample_address():
    return "0xC79BFBF4e4824Cdb65C71f2eeb2D7f2db5dA1fB8"
