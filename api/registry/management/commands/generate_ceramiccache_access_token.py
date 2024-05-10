from datetime import timedelta
from django.core.management.base import BaseCommand

from ceramic_cache.api.v1 import DbCacheToken


class LongLivedToken(DbCacheToken):
    lifetime: timedelta = timedelta(days=100 * 365)


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--address",
            type=str,
            help="""Address of the user for whom to generate the access token.""",
            required=True,
        )

    def handle(self, *args, **kwargs):
        address = kwargs["address"].lower()
        self.stdout.write(f"Generating long-lived access token for {address}")

        token = LongLivedToken()
        token["did"] = f"did:pkh:eip155:1:{address}"

        self.stdout.write("Access token:")
        self.stdout.write(f"{token.access_token}")
