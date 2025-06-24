from django.core.management.base import BaseCommand
from django.db import transaction

from registry.models import HumanPointsMultiplier, HumanPointsCommunityQualifiedUsers


class Command(BaseCommand):
    help = 'Backfill multipliers for returning users based on passing scores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process in each batch (default: 1000)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write("Finding addresses with passing scores in human_points_program communities...")
        
        # Find all unique addresses with passing scores
        qualified_addresses = (
            HumanPointsCommunityQualifiedUsers.objects
            .values_list('address', flat=True)
            .distinct()
        )
        
        total_qualified = qualified_addresses.count()
        self.stdout.write(f"Found {total_qualified} qualified addresses")
        
        # Get existing multipliers to exclude
        existing_multipliers = set(
            HumanPointsMultiplier.objects.values_list('address', flat=True)
        )
        self.stdout.write(f"Found {len(existing_multipliers)} existing multipliers")
        
        # Find addresses that need multipliers
        addresses_to_create = []
        for address in qualified_addresses.iterator(chunk_size=batch_size):
            if address not in existing_multipliers:
                addresses_to_create.append(address)
        
        self.stdout.write(f"Need to create multipliers for {len(addresses_to_create)} addresses")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            # Show sample of addresses that would be updated
            sample_size = min(10, len(addresses_to_create))
            if sample_size > 0:
                self.stdout.write("Sample addresses that would receive multipliers:")
                for addr in addresses_to_create[:sample_size]:
                    self.stdout.write(f"  - {addr}")
                if len(addresses_to_create) > sample_size:
                    self.stdout.write(f"  ... and {len(addresses_to_create) - sample_size} more")
        else:
            # Process in batches to avoid memory issues
            created_count = 0
            failed_count = 0
            
            for i in range(0, len(addresses_to_create), batch_size):
                batch = addresses_to_create[i:i + batch_size]
                multipliers = [
                    HumanPointsMultiplier(address=addr, multiplier=2)
                    for addr in batch
                ]
                
                try:
                    with transaction.atomic():
                        HumanPointsMultiplier.objects.bulk_create(
                            multipliers,
                            ignore_conflicts=True
                        )
                    created_count += len(batch)
                    self.stdout.write(f"Processed batch {i // batch_size + 1}: {len(batch)} addresses")
                except Exception as e:
                    failed_count += len(batch)
                    self.stdout.write(
                        self.style.ERROR(f"Failed to process batch {i // batch_size + 1}: {str(e)}")
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
        
        # Summary statistics
        self.stdout.write("\nSummary:")
        self.stdout.write(f"  Total qualified addresses: {total_qualified}")
        self.stdout.write(f"  Existing multipliers: {len(existing_multipliers)}")
        self.stdout.write(f"  New multipliers needed: {len(addresses_to_create)}")
        if not dry_run:
            self.stdout.write(f"  Successfully created: {created_count}")
            if failed_count > 0:
                self.stdout.write(f"  Failed to create: {failed_count}")