import csv
import json
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from registry.api.utils import with_read_db
from registry.models import Community, Event
from v2.api.api_stamps import EventFilter


class Command(BaseCommand):
    help = "Compare scores between two dates and output results to CSV"

    def extract_score_data(self, data):
        """Helper function to extract score data from event"""
        if isinstance(data, str):
            return json.loads(data)
        return data

    def get_score(self, address, community, created_at):
        """Get score for an address at a specific date"""
        filterset = EventFilter(
            data={
                "community__id": community.id,
                "action": Event.Action.SCORE_UPDATE,
                "address": address,
                "created_at__lte": created_at,
            },
            queryset=with_read_db(Event),
        )
        score_event = filterset.qs.order_by("-created_at").first()
        if not score_event:
            return None

        score_data = self.extract_score_data(score_event.data)

        return score_data["fields"]["evidence"]["rawScore"]

    def handle(self, *args, **options):
        # Hardcoded data - replace with your actual addresses
        address_data = [
            # address, submitted_onchain
            ["0x123...", True],
        ]

        # Define dates for comparison
        pre_date = datetime(2025, 1, 5, tzinfo=timezone.utc)
        post_date = datetime(2025, 1, 7, tzinfo=timezone.utc)

        # Get your community instance - replace with actual way to get community
        community = Community.objects.get(id=7922)

        # Prepare CSV output
        output_file = "score_comparison.csv"
        with open(output_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                ["address", "pre_rescore", "post_rescore", "submitted_onchain"]
            )

            for address, submitted_onchain in address_data:
                try:
                    pre_score = self.get_score(address, community, pre_date)
                    post_score = self.get_score(address, community, post_date)

                    writer.writerow(
                        [
                            address,
                            pre_score if pre_score is not None else "N/A",
                            post_score if post_score is not None else "N/A",
                            submitted_onchain,
                        ]
                    )

                    self.stdout.write(f"Processed {address}")
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing {address}: {str(e)}")
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully generated comparison CSV: {output_file}")
        )
