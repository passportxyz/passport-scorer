import os

REGISTRY_SCORER_ID = os.environ.get("REGISTRY_SCORER_ID")
REGISTRY_ADDRESS = os.environ.get("REGISTRY_ADDRESS")
REGISTRY_ROUND_ID = os.environ.get("REGISTRY_ROUND_ID")
REGISTRY_API_KEY = os.environ.get("REGISTRY_API_KEY")

CERAMIC_CACHE_JWT_TOKEN = os.environ.get("CERAMIC_CACHE_JWT_TOKEN")
CERAMIC_CACHE_ADDRESS = os.environ.get("CERAMIC_CACHE_ADDRESS")


stamps = [
    {
        "provider": "GitcoinContributorStatistics#totalContributionAmountGte#10",
    }
]

authenticate_payload = {
    "signatures": [
        {
            "protected": "xxxxxx",
            "signature": "xxxxxx",
        }
    ],
    "payload": "xxxxxx",
    "cid": [
        1,
        2,
        3,
    ],
    "cacao": [
        1,
        2,
        3,
    ],
    "issuer": "did:pkh:eip155:1:0x123",
    "nonce": "123456",
}


def get_config(base_url: str, base_url_xyz: str) -> dict:
    return {
        # Public API
        "registry": {
            "urls": {
                # No authentication
                ("GET", "/registry/signing-message"): {
                    "url": f"{base_url}registry/signing-message",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/registry/gtc-stake/{address}/{round_id}"): {
                    "url": f"{base_url}registry/gtc-stake/{REGISTRY_ADDRESS}/{REGISTRY_ROUND_ID}",
                    "success_http_statues": [200],
                },
                # requires authentication
                ("POST", "/registry/submit-passport"): {
                    "payload": {
                        "address": REGISTRY_ADDRESS,
                        "scorer_id": REGISTRY_SCORER_ID,
                    },
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "url": f"{base_url}registry/submit-passport",
                    "success_http_statues": [200],
                },
                ("GET", "/registry/score/{scorer_id}/history"): {
                    "url": f"{base_url}registry/score/{REGISTRY_SCORER_ID}/history?limit=1000",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/registry/score/{scorer_id}/{address}"): {
                    "url": f"{base_url}registry/score/{REGISTRY_SCORER_ID}/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/registry/score/{scorer_id}"): {
                    "url": f"{base_url}registry/score/{REGISTRY_SCORER_ID}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/registry/stamps/{address}"): {
                    "url": f"{base_url}registry/stamps/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/registry/stamp-metadata"): {
                    "url": f"{base_url}registry/stamp-metadata",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
            },
        },
        "registry_v2": {
            "skip": True,
            "urls": {},
        },
        # Passport Admin
        # Use custom JWT token here, and the same for any other API groups
        "ceramic-cache": {
            "urls": {
                # No auth required
                ("GET", "/ceramic-cache/stamp"): {
                    "url": f"{base_url}ceramic-cache/stamp?address={CERAMIC_CACHE_ADDRESS}",
                },
                ("GET", "/ceramic-cache/weights"): {
                    "url": f"{base_url}ceramic-cache/weights",
                },
                # Auth required
                ("GET", "/ceramic-cache/stake/gtc"): {
                    "url": f"{base_url}ceramic-cache/stake/gtc",
                    "http_headers": {
                        "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    },
                },
                ("GET", "/ceramic-cache/score/{address}"): {
                    "url": f"{base_url}ceramic-cache/score/{CERAMIC_CACHE_ADDRESS}",
                    "http_headers": {
                        "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    },
                },
                ("GET", "/ceramic-cache/tos/accepted/{tos_type}/{address}"): {
                    "url": f"{base_url}ceramic-cache/tos/accepted/ISI/{CERAMIC_CACHE_ADDRESS}",
                    "http_headers": {
                        "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    },
                },
                ("GET", "/ceramic-cache/tos/message-to-sign/{tos_type}/{address}"): {
                    "url": f"{base_url}ceramic-cache/tos/message-to-sign/IST/{CERAMIC_CACHE_ADDRESS}",
                    "http_headers": {
                        "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    },
                },
                ("PATCH", "/ceramic-cache/stamps/bulk/meta/compose-db"): {
                    "url": f"{base_url}ceramic-cache/stamps/bulk/meta/compose-db",
                    "http_headers": {
                        "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    },
                    "payload": [],
                },
                ("GET", "/ceramic-cache/score/{scorer_id}/{address}"): {
                    "skip": True,  # Skipping because uptime robot api rejects creating multiple monitors on same endpoint
                },
                ("POST", "/ceramic-cache/score/{address}"): {
                    # TODO: do we still use this POST API ???
                    "skip": True,  # Skipping because uptime robot api rejects creating multiple monitors on same endpoint
                    "url": f"{base_url}ceramic-cache/score/{CERAMIC_CACHE_ADDRESS}",
                    "http_headers": {
                        "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    },
                    "payload": {"alternate_scorer_id": REGISTRY_SCORER_ID},
                },
                ("POST", "/ceramic-cache/stamps/bulk"): {
                    "skip": True,  # Skipping because uptime robot api rejects creating multiple monitors on same endpoint
                    # "url": f"{base_url}ceramic-cache/stamps/bulk",
                    # "http_headers": {
                    #     "Authorization": f"Bearer {CERAMIC_CACHE_JWT_TOKEN}"
                    # },
                    # "payload": stamps,
                },
                ("PATCH", "/ceramic-cache/stamps/bulk"): {
                    "skip": True,  # Skipping because uptime robot api rejects creating multiple monitors on same endpoint
                },
                ("DELETE", "/ceramic-cache/stamps/bulk"): {
                    "skip": True,  # Skipping because uptime robot api rejects creating multiple monitors on same endpoint
                },
                ("POST", "/ceramic-cache/authenticate"): {
                    "skip": True,  # Skipping because uptime robot api rejects creating multiple monitors on same endpoint
                },
                ("POST", "/ceramic-cache/tos/signed-message/{tos_type}/{address}"): {
                    "skip": True,  # Skipping because we would need to post a wallet signature here
                },
            },
        },
        "passport-admin": {
            "skip": True,
            "urls": {},
        },
        "v2": {
            "urls": {
                ("GET", "/v2/stamps/{scorer_id}/score/{address}"): {
                    "url": f"{base_url_xyz}v2/stamps/{REGISTRY_SCORER_ID}/score/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/v2/stamps/{scorer_id}/score/{address}/history"): {
                    "url": f"{base_url_xyz}v2/stamps/{REGISTRY_SCORER_ID}/score/{REGISTRY_ADDRESS}/history",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/v2/stamps/{address}"): {
                    "url": f"{base_url_xyz}v2/stamps/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/v2/stamps/metadata"): {
                    "url": f"{base_url_xyz}v2/metadata",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
                ("GET", "/v2/models/score/{address}"): {
                    "url": f"{base_url_xyz}v2/models/score/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "success_http_statues": [200],
                },
            },
        },
    }
