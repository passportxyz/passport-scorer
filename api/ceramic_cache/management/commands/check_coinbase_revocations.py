from datetime import UTC, datetime
from typing import List

import requests
from django.core.management.base import BaseCommand

from ceramic_cache.models import CeramicCache, Revocation
from passport_admin.models import LastScheduledRun

QUERY_URL = "https://base.easscan.org/graphql"
COINBASE_ATTESTER = "0x357458739F90461b99789350868CD7CF330Dd7EE"
SCHEMA = "0xf8b05c79f090979bf4a80270aba232dff11a10d9ca55c4f88de95317970f0de9"

COINBASE_STAMP_PROVIDER = "CoinbaseDualVerification"

TASK_NAME = "check_coinbase_revocations"


class Command(BaseCommand):
    help = "Copy latest stamp weights to eligible scorers and launch rescore"

    def handle(self, *args, **kwargs):
        self.stdout.write("Running ...")

        is_first_run = not LastScheduledRun.objects.filter(name=TASK_NAME).exists()

        if is_first_run:
            start_time = datetime.fromtimestamp(0).astimezone(UTC)
        else:
            start_time = LastScheduledRun.objects.get(name=TASK_NAME).last_run

        end_time = datetime.now(UTC)

        self.stdout.write(
            self.style.SUCCESS(
                f"Checking for revoked attestations between [{start_time}, {end_time})"
            )
        )

        revoked_addresses = self.get_revoked_attestation_addresses(start_time, end_time)

        self.stdout.write(
            self.style.NOTICE(f"Found {len(revoked_addresses)} revoked addresses")
        )

        for address in revoked_addresses:
            stamps = CeramicCache.objects.filter(
                address=address,
                provider=COINBASE_STAMP_PROVIDER,
                revocation__isnull=True,
            )

            for stamp in stamps:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Revoking stamp with proof_value={stamp.proof_value} for address={address}"
                    )
                )

                Revocation.objects.create(
                    proof_value=stamp.proof_value, ceramic_cache=stamp
                )

        LastScheduledRun.objects.update_or_create(
            name=TASK_NAME, defaults={"last_run": end_time}
        )

        self.stdout.write(self.style.SUCCESS("Done"))

    def get_revoked_attestation_addresses(
        self, start_time: datetime, end_time: datetime
    ) -> List[str]:
        start_time_unix = int(start_time.timestamp())
        end_time_unix = int(end_time.timestamp())

        query = f"""
            query RevocationsQuery {{
              attestations(
                where: {{
                  revoked: {{ equals: true }}
                  attester: {{ equals: "{COINBASE_ATTESTER}" }}
                  revocationTime: {{ gte: {start_time_unix}, lt: {end_time_unix} }}
                  schemaId: {{
                    equals: "{SCHEMA}"
                  }}
                }}
              ) {{
                recipient
              }}
            }}
        """

        response = requests.post(
            QUERY_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise Exception(f"Failed to query attestations: {response.text}")

        response_body = response.json()

        return [
            attestation["recipient"].lower()
            for attestation in response_body["data"]["attestations"]
        ]
