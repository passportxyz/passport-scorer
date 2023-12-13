import json

from cgrants.models import Subscription
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Import GGX Round contribution and squelch data."

    def add_arguments(self, parser):
        parser.add_argument(
                "--config",
                type=str,
                help="""Configure the import. JSON object containing:
                                {
                                    // links to round ids from the latest round
                                    "gg_round_ids": "0xaddress[]",
                                }
                                """,
            )

    def handle(self, *args, **options):
        config = options["config"]
        self.stdout.write(f"config : {config}")

        gg_config = json.loads(config)

        round_ids = gg_config["gg_round_ids"]

        for round in round_ids:
