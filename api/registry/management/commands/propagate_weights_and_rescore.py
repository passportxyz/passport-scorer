from account.deduplication import Rules
from account.models import Community
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from registry.models import Score
from registry.tasks import score_registry_passport
from scorer_weighted.models import BinaryWeightedScorer, WeightedScorer


class Command(BaseCommand):
    help = "Copy latest stamp weights to eligible scorers and launch rescore"

    def add_arguments(self, parser):
        # Optional argument
        parser.add_argument(
            "--update_all_scores",
            type=str,
            choices=["True", "False"],
            default="True",
            help="Flag to update all scores.",
        )

    def handle(self, *args, **kwargs):
        update_all_scores = kwargs.get("update_all_scores", True)
        weights = settings.GITCOIN_PASSPORT_WEIGHTS
        threshold = settings.GITCOIN_PASSPORT_THRESHOLD

        community_ids = self.get_eligible_communities()

        self.update_scorers(community_ids, weights, threshold)
        if update_all_scores:
            self.update_scores(community_ids)

    @staticmethod
    def get_eligible_communities() -> QuerySet[Community]:
        return Community.objects.filter(rule=Rules.LIFO.value)

    def update_scorers(self, communities: QuerySet[Community], weights, threshold):
        filter = {"scorer_ptr__community__in": communities}

        binary_weighted_scorers = BinaryWeightedScorer.objects.filter(**filter)
        weighted_scorers = WeightedScorer.objects.filter(**filter)

        weighted_scorers.update(weights=weights)
        binary_weighted_scorers.update(weights=weights, threshold=threshold)

        print(
            "Updated scorers:",
            weighted_scorers.count() + binary_weighted_scorers.count(),
        )

    def update_scores(self, communities: QuerySet[Community]):
        scores = Score.objects.filter(
            passport__community__in=communities
        ).select_related("passport")

        scores.update(status=Score.Status.BULK_PROCESSING)

        for score in scores:
            passport = score.passport
            passport.requires_calculation = True
            passport.save()

            score_registry_passport.delay(passport.community.pk, passport.address)

        print("Updating scores:", scores.count())
