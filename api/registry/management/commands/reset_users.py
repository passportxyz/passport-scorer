from account.models import Community
from ceramic_cache.models import CeramicCache
from django.core.management.base import BaseCommand
from registry.models import Passport, Score, Stamp
from registry.utils import get_utc_time


class Command(BaseCommand):
    help = "Removes stamp data and sets score to 0 for users in the provided list"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="""Batch size for rescoring""",
        )
        parser.add_argument(
            "--address-list",
            type=str,
            help="""Local path to a file containing a list of addresses to reset, one address per line""",
            required=True,
        )

    def handle(self, *args, **kwargs):
        self.stdout.write("Running ...")
        self.stdout.write(f"args     : {args}")
        self.stdout.write(f"kwargs   : {kwargs}")

        batch_size = kwargs["batch_size"]

        with open(kwargs["address_list"]) as addresses_file:
            addresses_batch = []
            for line_number, line in enumerate(addresses_file):
                addresses_batch.append(line.strip().lower())
                if (line_number + 1) % batch_size == 0:
                    self.reset_addresses(addresses_batch)
                    addresses_batch = []

            if addresses_batch:
                self.reset_addresses(addresses_batch)

    def reset_addresses(self, addresses):
        self.stdout.write(
            f"Resetting addresses - for batch of {len(addresses)} addresses ending with {addresses[-1]}"
        )

        try:
            now = get_utc_time()
            self.stdout.write("Resetting addresses - deleting ceramic cache entries")
            ceramic_cache_entries = CeramicCache.objects.filter(
                address__in=addresses, deleted_at__isnull=True
            )
            ceramic_cache_entries.update(deleted_at=now, updated_at=now)

            passports = Passport.objects.filter(address__in=addresses).order_by(
                "community"
            )
            passport_ids = passports.values_list("id", flat=True)

            self.stdout.write("Resetting addresses - deleting stamps")

            stamps = Stamp.objects.filter(passport_id__in=passport_ids)
            stamps.delete()

            self.stdout.write("Resetting addresses - recalculating scores")

            current_community_id = None
            community_passports = []
            for passport in passports:
                if (
                    passport.community_id != current_community_id
                    and current_community_id
                ):
                    self.reset_scores(community_passports, current_community_id)
                    community_passports = []

                community_passports.append(passport)
                current_community_id = passport.community_id

            if community_passports:
                self.reset_scores(community_passports, current_community_id)

        except Exception as e:
            self.stdout.write(f"Resetting addresses - error: {e}")
            raise e
        else:
            self.stdout.write("Resetting addresses - batch complete")

    def reset_scores(self, passports, community_id):
        community = Community.objects.get(pk=community_id)
        passport_ids = [p.pk for p in passports]

        self.stdout.write(
            f"Resetting addresses - recalculating scores for {len(passport_ids)} passports in community ID {community.pk}"
        )

        scorer = community.get_scorer()
        calculated_scores = scorer.recompute_score(passport_ids, {}, community_id)

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
                scoreData.evidence[0].as_dict() if scoreData.evidence else None
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
