from .env import env

ETHEREUM_MODEL_ENDPOINT = env(
    "ETHEREUM_MODEL_ENDPOINT", default="http://localhost:5007/eth-stamp-predict"
)
NFT_MODEL_ENDPOINT = env(
    "NFT_MODEL_ENDPOINT", default="http://localhost:5003/nft-model-predict"
)
ZKSYNC_MODEL_ENDPOINT = env(
    "ZKSYNC_MODEL_ENDPOINT", default="http://localhost:5006/zksync-model-predict"
)
POLYGON_MODEL_ENDPOINT = env(
    "POLYGON_MODEL_ENDPOINT", default="http://localhost:5005/polygon-model-predict"
)
ARBITRUM_MODEL_ENDPOINT = env(
    "ARBITRUM_MODEL_ENDPOINT", default="http://localhost:5002/arbitrum-model-predict"
)
OPTIMISM_MODEL_ENDPOINT = env(
    "OPTIMISM_MODEL_ENDPOINT", default="http://localhost:5004/op-model-predict"
)
AGGREGATE_MODEL_ENDPOINT = env(
    "AGGREGATE_MODEL_ENDPOINT", default="http://localhost:5001/aggregate-model-predict"
)

AGGREGATE_MODEL_NAME = "aggregate"


MODEL_AGGREGATION_NAMES = {
    "zksync": "zk",
    "polygon": "polygon",
    "ethereum_activity": "eth",
    "arbitrum": "arb",
    "optimism": "op",
}

MODEL_ENDPOINTS = {
    "ethereum_activity": ETHEREUM_MODEL_ENDPOINT,
    "nft": NFT_MODEL_ENDPOINT,
    "zksync": ZKSYNC_MODEL_ENDPOINT,
    "polygon": POLYGON_MODEL_ENDPOINT,
    "arbitrum": ARBITRUM_MODEL_ENDPOINT,
    "optimism": OPTIMISM_MODEL_ENDPOINT,
    AGGREGATE_MODEL_NAME: AGGREGATE_MODEL_ENDPOINT,
}

MODEL_ENDPOINTS_DEFAULT = "aggregate"

# This is really only here to allow for testing with multiple models
# while the single-model restriction is in place. Once lifted,
# this can be removed
ONLY_ONE_MODEL = True
