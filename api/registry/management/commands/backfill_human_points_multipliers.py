from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from account.models import Community
from registry.models import (
    HumanPointsCommunityQualifiedUsers,
    HumanPointsMultiplier,
    Score,
)


class Command(BaseCommand):
    help = "Backfill multipliers for returning users based on passing scores"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process in each batch (default: 1000)",
        )
        parser.add_argument(
            "--scorer-id",
            type=int,
            default=335,
            help="ID of the binary scorer to check for passing scores (default: 335)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        scorer_id = options["scorer_id"]

        self.stdout.write(
            f"Finding addresses with passing binary scores in scorer {scorer_id}..."
        )

        # Find all unique addresses with passing binary score (1) in the specified scorer
        # This is typically a binary scorer where score=1 means pass
        qualified_addresses = (
            Score.objects.filter(
                passport__community_id=scorer_id,
                score=Decimal("1"),  # Binary pass score
            )
            .values_list("passport__address", flat=True)
            .distinct()
        )

        # Convert to list to get count and for batching
        qualified_addresses = list(qualified_addresses)
        total_qualified = len(qualified_addresses)
        self.stdout.write(
            f"Found {total_qualified} qualified addresses with binary score = 1 in scorer {scorer_id}"
        )

        # Check how many already have multipliers
        existing_multipliers = HumanPointsMultiplier.objects.filter(
            address__in=qualified_addresses
        ).values_list("address", flat=True)
        existing_count = len(existing_multipliers)
        to_create_count = total_qualified - existing_count

        self.stdout.write(f"Addresses already with multipliers: {existing_count}")
        self.stdout.write(f"Addresses needing multipliers: {to_create_count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            return

        # Process in batches to avoid memory issues
        created_count = 0
        failed_count = 0

        for i in range(0, len(qualified_addresses), batch_size):
            batch = qualified_addresses[i : i + batch_size]
            multipliers = [
                HumanPointsMultiplier(address=addr, multiplier=2) for addr in batch
            ]

            try:
                with transaction.atomic():
                    HumanPointsMultiplier.objects.bulk_create(
                        multipliers, ignore_conflicts=True
                    )
                created_count += len(batch)
                self.stdout.write(
                    f"Processed batch {i // batch_size + 1}: {len(batch)} addresses"
                )
            except Exception as e:
                failed_count += len(batch)
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to process batch {i // batch_size + 1}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete: Created {created_count} multipliers"
            )
        )
        if failed_count > 0:
            self.stdout.write(
                self.style.ERROR(f"Failed to create {failed_count} multipliers")
            )

        self.stdout.write("Done")
