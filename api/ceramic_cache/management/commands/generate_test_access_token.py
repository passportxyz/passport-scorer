from datetime import timedelta

from django.core.management.base import BaseCommand

from ceramic_cache.api.v1 import DbCacheToken


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--did", help="DID for which to issue access token", type=str, required=True
        )

    def handle(self, *args, **kwargs):
        DbCacheToken.lifetime = timedelta(days=356)
        token = DbCacheToken()
        token.access_token_class.lifetime = timedelta(days=356)

        token["did"] = kwargs["did"]

        self.stdout.write(f"Token: {token.access_token}")
