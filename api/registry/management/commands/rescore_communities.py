from django.core.management.base import BaseCommand

from account.models import Community
from registry.management.commands.recalculate_scores import recalculate_scores


class Command(BaseCommand):
    help = (
        "Recalculate scores for the given communities with their current weights. "
        "This is what the rescore queue consumer does; recalculate_scores also "
        "copies the latest weights first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--community-ids",
            type=str,
            required=True,
            help="Comma-separated community ids",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for rescoring",
        )

    def handle(self, *args, **options):
        community_ids = [id for id in options["community_ids"].split(",") if id]
        communities = Community.objects.filter(id__in=community_ids)
        recalculate_scores(communities, options["batch_size"], self.stdout)
