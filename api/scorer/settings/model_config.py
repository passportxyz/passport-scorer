from .env import env

ETHEREUM_MODEL_ENDPOINT = env(
    "ETHEREUM_MODEL_ENDPOINT", default="http://localhost:80/ethereum"
)
NFT_MODEL_ENDPOINT = env("NFT_MODEL_ENDPOINT", default="http://localhost:80/nft")
ZKSYNC_MODEL_ENDPOINT = env(
    "ZKSYNC_MODEL_ENDPOINT", default="http://localhost:80/zksync"
)
POLYGON_MODEL_ENDPOINT = env(
    "POLYGON_MODEL_ENDPOINT", default="http://localhost:80/zksync"
)
ARBITRUM_MODEL_ENDPOINT = env(
    "ARBITRUM_MODEL_ENDPOINT", default="http://localhost:80/zksync"
)
OPTIMISM_MODEL_ENDPOINT = env(
    "OPTIMISM_MODEL_ENDPOINT", default="http://localhost:80/zksync"
)

MODEL_ENDPOINTS = {
    "ethereum_activity": ETHEREUM_MODEL_ENDPOINT,
    "nft": NFT_MODEL_ENDPOINT,
    "zksync": ZKSYNC_MODEL_ENDPOINT,
    "polygon": POLYGON_MODEL_ENDPOINT,
    "arbitrum": ARBITRUM_MODEL_ENDPOINT,
    "optimism": OPTIMISM_MODEL_ENDPOINT,
}

MODEL_ENDPOINTS_DEFAULT = "ethereum_activity"
