import json
from datetime import datetime

from account.models import Community
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from registry.models import Passport, Score, Stamp
from registry.utils import get_utc_time
from scorer_weighted.models import BinaryWeightedScorer, RescoreRequest, WeightedScorer


class Command(BaseCommand):
    help = "Copy latest stamp weights to eligible scorers and launch rescore"

    def add_arguments(self, parser):
        # Optional argument
        parser.add_argument(
            "--filter-community-include",
            type=str,
            default="{}",
            help="""Filter as JSON formatted dict, this will be expanded and passed in directly to the django query `.filter`, for example: '{"id": excluded_community.id}'""",
        )
        parser.add_argument(
            "--filter-community-exclude",
            type=str,
            default="{}",
            help="""Filter as JSON formatted dict, this will be expanded and passed in directly to the django query `.exclude`, for example: '{"id": excluded_community.id}'""",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="""Batch size for recoring""",
        )
        parser.add_argument(
            "--only-weights",
            type=bool,
            default=False,
            choices=[True, False],
            help="""Only update weights, don't recalculate scores""",
        )

    def handle(self, *args, **kwargs):
        self.stdout.write("Running ...")
        self.stdout.write(f"args     : {args}")
        self.stdout.write(f"kwargs   : {kwargs}")
        filter = (
            json.loads(kwargs["filter_community_include"])
            if kwargs["filter_community_include"]
            else {}
        )
        exclude = (
            json.loads(kwargs["filter_community_exclude"])
            if kwargs["filter_community_exclude"]
            else {}
        )

        batch_size = kwargs["batch_size"]

        communities = (
            Community.objects.filter(**filter)
            .exclude(**exclude)
            .exclude(scorer__weightedscorer__exclude_from_weight_updates=True)
            .exclude(scorer__binaryweightedscorer__exclude_from_weight_updates=True)
        )

        self.stdout.write(f"Updating communities: {list(communities)}")

        # Update Score weights
        self.update_scorers(communities)

        if kwargs["only_weights"]:
            return

        self.stdout.write("Recalculating scores")

        return recalculate_scores(communities, batch_size, self.stdout)

    def update_scorers(self, communities: QuerySet[Community]):
        weights = settings.GITCOIN_PASSPORT_WEIGHTS
        threshold = settings.GITCOIN_PASSPORT_THRESHOLD

        filter = {"scorer_ptr__community__in": communities}

        binary_weighted_scorers = BinaryWeightedScorer.objects.filter(**filter)
        weighted_scorers = WeightedScorer.objects.filter(**filter)

        weighted_scorers.update(weights=weights)
        binary_weighted_scorers.update(weights=weights, threshold=threshold)


def recalculate_scores(communities, batch_size, outstream):
    count = 0
    start = datetime.now()

    rescore_request = RescoreRequest.objects.create(
        num_communities_requested=len(communities)
    )
    rescore_request.save()

    try:
        for idx, community in enumerate(communities):
            # Reset has_more and last_id for each community
            has_more = True
            last_id = 0
            scorer = community.get_scorer()
            outstream.write(
                f"""
Community:{community}
scorer type: {scorer.type}, {type(scorer)}"""
            )

            while has_more:
                outstream.write(
                    f"has more: {has_more} / last id: {last_id} / count: {count}"
                )
                passport_query = Passport.objects.order_by("id").select_related("score")
                if last_id:
                    passport_query = passport_query.filter(id__gt=last_id)
                passport_query = passport_query.filter(community=community)
                passports = list(passport_query[:batch_size].iterator())
                passport_ids = [p.id for p in passports]
                count += len(passports)
                has_more = len(passports) > 0
                if len(passports) > 0:
                    last_id = passport_ids[-1]
                    stamp_query = Stamp.objects.filter(passport_id__in=passport_ids)
                    stamps = {}
                    for s in stamp_query:
                        if s.passport_id not in stamps:
                            stamps[s.passport_id] = []
                        stamps[s.passport_id].append(s)
                    calculated_scores = scorer.recompute_score(
                        passport_ids, stamps, community.id
                    )
                    scores_to_update = []
                    scores_to_create = []

                    for p, scoreData in zip(passports, calculated_scores):
                        passport_scores = list(p.score.all())
                        if passport_scores:
                            score = passport_scores[0]
                            scores_to_update.append(score)
                        else:
                            score = Score(
                                passport=p,
                            )
                            scores_to_create.append(score)

                        score.score = scoreData.score
                        score.status = Score.Status.DONE
                        score.last_score_timestamp = get_utc_time()
                        score.evidence = (
                            scoreData.evidence[0].as_dict()
                            if scoreData.evidence
                            else None
                        )
                        score.error = None
                        score.stamp_scores = scoreData.stamp_scores

                    if scores_to_create:
                        Score.objects.bulk_create(scores_to_create)

                    if scores_to_update:
                        Score.objects.bulk_update(
                            scores_to_update,
                            [
                                "score",
                                "status",
                                "last_score_timestamp",
                                "evidence",
                                "error",
                                "stamp_scores",
                            ],
                        )

                elapsed = datetime.now() - start
                rate = "-"
                if count > 0:
                    rate = elapsed / count

                outstream.write(
                    f"""
Community id: {community}
Elapsed: {elapsed}
Count: {count}
Rate: {rate}
"""
                )
            rescore_request.num_communities_processed = idx + 1
            rescore_request.save()

    except Exception as e:
        rescore_request.status = RescoreRequest.Status.FAILED
        rescore_request.save()

        raise e

    rescore_request.status = RescoreRequest.Status.SUCCESS
    rescore_request.save()
