"""
Starts Cloud Run job executions from code running on Google Cloud.
"""

import requests

METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
RUN_API_URL = "https://run.googleapis.com/v2"


def run_job(job_name: str, args: list[str], timeout: float = 10) -> str:
    """
    Starts an execution of `job_name` with the container args replaced by
    `args`, as the runtime service account, and returns the name of the
    long-running operation. The job's command is fixed by its definition.
    """
    token_response = requests.get(
        METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"}, timeout=timeout
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]

    response = requests.post(
        f"{RUN_API_URL}/{job_name}:run",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"overrides": {"containerOverrides": [{"args": args}]}},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["name"]
