# pylint: disable=redefined-outer-name
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja_jwt.schema import RefreshToken
from web3 import Web3

from account.models import Account, AccountAPIKey, Community
from ceramic_cache.api.v1 import DbCacheToken
from registry.models import GTCStakeEvent, Passport, Score
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.config.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer_weighted.models import BinaryWeightedScorer, Scorer, WeightedScorer

User = get_user_model()

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

pytestmark = pytest.mark.django_db

my_mnemonic = settings.TEST_MNEMONIC


@pytest.fixture
def scorer_user():
    user = User.objects.create_user(username="testuser-1", password="12345")
    return user


@pytest.fixture
def access_token(scorer_user):
    refresh = RefreshToken.for_user(scorer_user)
    refresh["ip_address"] = "127.0.0.1"
    return refresh.access_token


@pytest.fixture
def scorer_account(scorer_user):
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    account = Account.objects.create(user=scorer_user, address=web3_account.address)
    return account


@pytest.fixture
def passport_holder_addresses():
    ret = []
    for i in range(10):
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
        account=scorer_account,
        name="Token for user 1",
        rate_limit="3/30seconds",
        analysis_rate_limit="3/30seconds",
    )
    return secret


@pytest.fixture
def scorer_api_key_no_permissions(scorer_account):
    (_, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account,
        name="Token for user 1",
        rate_limit="3/30seconds",
        read_scores=False,
    )
    return secret


@pytest.fixture
def weight_config():
    config = WeightConfiguration.objects.create(
        version="v1",
        threshold=20.0,
        active=True,
        description="Test",
    )

    for provider, weight in GITCOIN_PASSPORT_WEIGHTS.items():
        WeightConfigurationItem.objects.create(
            weight_configuration=config,
            provider=provider,
            weight=float(weight),
        )

    return config


@pytest.fixture
def scorer_community_with_binary_scorer(mocker, scorer_account, weight_config):
    scorer = BinaryWeightedScorer.objects.create(type=Scorer.Type.WEIGHTED_BINARY)

    community = Community.objects.create(
        name="My Binary Weighted Community",
        description="My Binary Weighted Community description",
        account=scorer_account,
        scorer=scorer,
    )
    return community


@pytest.fixture
def ui_scorer(scorer_community_with_binary_scorer):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.id
    return settings.CERAMIC_CACHE_SCORER_ID


@pytest.fixture
def scorer_community_with_weighted_scorer(mocker, scorer_account, weight_config):
    scorer = WeightedScorer.objects.create(type=Scorer.Type.WEIGHTED)

    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
        scorer=scorer,
    )
    return community


@pytest.fixture
def scorer_community(scorer_account, weight_config):
    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
    )
    return community


@pytest.fixture
def scorer_passport(scorer_account, scorer_community):
    passport = Passport.objects.create(
        address=scorer_account.address,
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
def scorer_community_with_gitcoin_default(mocker, scorer_account, weight_config):
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
def api_key():
    user = User.objects.create_user(username="testuser-1", password="12345")
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    account = Account.objects.create(user=user, address=web3_account.address)
    (_, secret) = AccountAPIKey.objects.create_key(
        account=account, name="Token for user 1"
    )

    return secret


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


@pytest.fixture
def sample_token(sample_address):
    token = DbCacheToken()
    token["token_type"] = "access"
    token["did"] = f"did:pkh:eip155:1:{sample_address.lower()}"

    return str(token)


@pytest.fixture
def gtc_staking_response():
    user_address = "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"
    # Make sure this one is filtered out because it's below the minimum amount
    # 1 self stake of 2
    GTCStakeEvent.objects.create(
        id=16,
        event_type="SelfStake",
        round_id=1,
        staker="0x976EA74026E726554dB657fA54763abd0C3a0aa9",
        address=None,
        amount=2,
        staked=True,
        block_number=16,
        tx_hash="0x431",
    )

    # 1 self stake of 125
    GTCStakeEvent.objects.create(
        id=17,
        event_type="SelfStake",
        round_id=1,
        staker=user_address,
        address=None,
        amount=125,
        staked=True,
        block_number=16,
        tx_hash="0x931",
    )

    # Stake >= 5 GTC on at least 1 account
    GTCStakeEvent.objects.create(
        id=18,
        event_type="Xstake",
        round_id=1,
        staker=user_address,
        address="0x70Ac77777e4AbE2d293586A1f4F9C73e5512121e",
        amount=5,
        staked=True,
        block_number=16,
        tx_hash="0xa32",
    )

    # Have 1 account stake >= 5 GTC on you
    GTCStakeEvent.objects.create(
        id=19,
        event_type="Xstake",
        round_id=1,
        staker="0x70Ac77777e4AbE2d293586A1f4F9C73e5512121e",
        address=user_address,
        amount=5,
        staked=True,
        block_number=16,
        tx_hash="0xb32",
    )
    # Stake 10 GTC on at least 2 accounts
    # Create a loop to catch each 2
    for i in range(0, 2, 1):
        GTCStakeEvent.objects.create(
            id=i + 110,
            event_type="Xstake",
            round_id=1,
            staker=user_address,
            address=f"0x90Ac99999e4AbE2d293586A1f4F9C73e551216b{i}",
            amount=10,
            staked=True,
            block_number=16,
            tx_hash=f"0x79{i}",
        )
    # 2 accounts stake 10 GTC on you
    for i in range(0, 2, 1):
        GTCStakeEvent.objects.create(
            id=i + 33,
            event_type="Xstake",
            round_id=1,
            address=user_address,
            staker=f"0x90Ac99999e4AbE2d293586A1f4F9C73e551912c{i}",
            amount=10,
            staked=True,
            block_number=16,
            tx_hash=f"0x39{i}",
        )

    # Receive stakes from 5 unique users, each staking a minimum of 20 GTC on you.
    for i in range(0, 5, 1):
        GTCStakeEvent.objects.create(
            id=i + 20,
            event_type="Xstake",
            round_id=1,
            staker=f"0x90Ac99999e4AbE2d293586A1f4F9C73e551212e{i}",
            address=user_address,
            amount=21,
            staked=True,
            block_number=16,
            tx_hash=f"0x89{i}",
        )
