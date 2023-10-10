import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from account.deduplication import Rules
from account.models import Community
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from registry.atasks import acalculate_score
from registry.models import Passport, Score, Stamp
from registry.tasks import score_registry_passport
from registry.utils import get_utc_time
from scorer_weighted.models import BinaryWeightedScorer, WeightedScorer


class Command(BaseCommand):
    help = "Copy latest stamp weights to eligible scorers and launch rescore"

    def add_arguments(self, parser):
        # Optional argument
        parser.add_argument(
            "--filter-community-include",
            type=str,
            default="{}",
            help="""Filter:
                            {
                                "name": "<model name> - for example ceramic_cache.CeramicCache",
                                "filename": "custom filename for the export, otherwise the tablename will be used by default",
                                "filter": "<filter to apply to query - this dict will be passed into the `filter(...) query method`>,
                                "extra-args": "<extra args to the s3 upload. This can be used to set dump file permissions, see: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/upload_file.html>"
                                "select_related":["<array of releated field names that should be expanded and included in the dump">]
                            }
                            """,
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="""Batch size for recoring""",
        )

    def handle(self, *args, **kwargs):
        # update_all_scores = kwargs.get("update_all_scores", True)
        # weights = settings.GITCOIN_PASSPORT_WEIGHTS
        # threshold = settings.GITCOIN_PASSPORT_THRESHOLD

        print("Running ...")
        print("args     :", args)
        print("kwargs   :", kwargs)
        filter = (
            json.loads(kwargs["filter_community_include"])
            if kwargs["filter_community_include"]
            else {}
        )
        batch_size = kwargs["batch_size"]
        has_more = True
        last_id = None
        count = 0
        start = datetime.now()
        communities = Community.objects.filter(**filter)
        print("recalculate_scores => 1")
        print("recalculate_scores => 1", list(communities))
        for community in communities:
            scorer = community.get_scorer()
            print("scorer type", scorer.type)
            print("scorer type", type(scorer))
            print("recalculate_scores => 2")
            while has_more:
                print(f"{has_more} / {last_id} / {count}")
                passport_query = Passport.objects.order_by("id").select_related("score")
                if last_id:
                    passport_query = passport_query.filter(id__gt=last_id)
                passport_query = passport_query.filter(community=community)
                passports = list(passport_query[:batch_size].iterator())
                passport_ids = [p.id for p in passports]
                count += len(passports)
                has_more = len(passports) > 0
                print("recalculate_scores => 3")
                if len(passports) > 0:
                    last_id = passport_ids[-1]
                    stamp_query = Stamp.objects.filter(passport_id__in=passport_ids)
                    stamps = {}
                    for s in stamp_query:
                        if s.passport_id not in stamps:
                            stamps[s.passport_id] = []
                        stamps[s.passport_id].append(s)
                    calculated_scores = scorer.recompute_score(passport_ids, stamps)
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
                        score.points = scoreData.points

                    print("scores_to_create : ", scores_to_create)
                    print("scores_to_update : ", scores_to_update)
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
                                "points",
                            ],
                        )

                elapsed = datetime.now() - start
                print("*" * 80)
                print(f"Elapsed: {elapsed}")
                print(f"Count: {count}")
                print(f"Rate: {elapsed / count}")
                print("*" * 80)
                # has_more = has_more and count < 100
                print(f"Has more: {has_more}")
