import os

REGISTRY_SCORER_ID = os.environ.get("REGISTRY_SCORER_ID")
REGISTRY_ADDRESS = os.environ.get("REGISTRY_ADDRESS")
REGISTRY_ROUND_ID = os.environ.get("REGISTRY_ROUND_ID")
REGISTRY_API_KEY = os.environ.get("REGISTRY_API_KEY")


def get_config(base_url: str) -> dict:
    return {
        # Public API
        "registry": {
            "urls": {
                # No authentication
                ("GET", "/registry/signing-message"): {
                    "url": f"{base_url}registry/signing-message",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                },
                ("GET", "/registry/gtc-stake/{address}/{round_id}"): {
                    "url": f"{base_url}registry/gtc-stake/{REGISTRY_ADDRESS}/{REGISTRY_ROUND_ID}"
                },
                # requires authentication
                ("POST", "/registry/submit-passport"): {
                    "payload": {
                        "address": REGISTRY_ADDRESS,
                        "scorer_id": REGISTRY_SCORER_ID,
                    },
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                    "url": f"{base_url}registry/submit-passport",
                },
                ("GET", "/registry/score/{scorer_id}/history"): {
                    "url": f"{base_url}registry/score/{REGISTRY_SCORER_ID}/history?limit=1000",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                },
                ("GET", "/registry/score/{scorer_id}/{address}"): {
                    "url": f"{base_url}registry/score/{REGISTRY_SCORER_ID}/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                },
                ("GET", "/registry/score/{scorer_id}"): {
                    "url": f"{base_url}registry/score/{REGISTRY_SCORER_ID}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                },
                ("GET", "/registry/stamps/{address}"): {
                    "url": f"{base_url}stamps/{REGISTRY_ADDRESS}",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                },
                ("GET", "/registry/stamp-metadata"): {
                    "url": f"{base_url}registry/stamp-metadata",
                    "http_headers": {"X-API-Key": REGISTRY_API_KEY},
                },
            },
        },
        # Passport Admin
        # Use custom JWT token here, and the same for any other API groups
        "ceramic-cache": {
            "urls": {},
        },
        "passport-admin": {
            "urls": {},
        },
    }
