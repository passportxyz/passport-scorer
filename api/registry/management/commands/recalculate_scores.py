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
        count = 0
        start = datetime.now()
        communities = Community.objects.filter(**filter).exclude(**exclude)
        self.stdout.write(f"Recalculating scores for communities: {list(communities)}")
        for community in communities:
            # Reset has_more and last_id for each community
            has_more = True
            last_id = 0
            scorer = community.get_scorer()
            self.stdout.write(
                f"""
Community:{community}
scorer type: {scorer.type}, {type(scorer)}"""
            )
            while has_more:
                self.stdout.write(
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
                rate = "-"
                if count > 0:
                    rate = elapsed / count
                self.stdout.write(
                    f"""
Community id: {community}
Elapsed: {elapsed}
Count: {count}
Rate: {rate}
"""
                )
