import csv
import json
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from registry.models import Score


class Command(BaseCommand):
    help = """
    Export addresses with recent scores for load testing.

    This outputs addresses that:
    - Were scored recently (within --days parameter)
    - Have non-zero scores (actual stamps)

    Example usage:
        python manage.py export_addresses_for_load_testing --days 7 --limit 200
        python manage.py export_addresses_for_load_testing --days 30 --format json --output addresses.json
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to look back for recent scores (default: 7)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Maximum number of addresses to export (default: 200)",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["csv", "json", "jsonl", "text"],
            default="csv",
            help="Output format: csv, json, jsonl, or text (default: csv)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output file path (default: stdout)",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=0.0,
            help="Minimum score threshold (default: 0.0 for any non-zero score)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        limit = options["limit"]
        format_type = options["format"]
        output_file = options["output"]
        min_score = options["min_score"]

        # Calculate the cutoff date
        since_date = timezone.now() - timedelta(days=days)

        self.stdout.write(f"Querying addresses scored in the last {days} days...")
        self.stdout.write(f"Minimum score: {min_score}")
        self.stdout.write(f"Limit: {limit}")

        # Query for addresses with recent scores
        scores = (
            Score.objects.filter(
                last_score_timestamp__gte=since_date, score__gt=min_score
            )
            .select_related("passport")
            .order_by("-last_score_timestamp")[:limit]
        )

        # Extract addresses and score data
        results = []
        for score in scores:
            results.append(
                {
                    "address": score.passport.address,
                    "score": str(score.score),
                    "last_score_timestamp": score.last_score_timestamp.isoformat(),
                }
            )

        self.stdout.write(f"Found {len(results)} addresses")

        # Determine output stream
        if output_file:
            output_stream = open(output_file, "w")
            self.stdout.write(f"Writing to {output_file}...")
        else:
            output_stream = sys.stdout

        try:
            # Output in the requested format
            if format_type == "csv":
                writer = csv.DictWriter(
                    output_stream,
                    fieldnames=["address", "score", "last_score_timestamp"],
                )
                writer.writeheader()
                writer.writerows(results)

            elif format_type == "json":
                json.dump(
                    [r["address"] for r in results], output_stream, indent=2
                )
                output_stream.write("\n")

            elif format_type == "jsonl":
                for result in results:
                    json.dump(result, output_stream)
                    output_stream.write("\n")

            elif format_type == "text":
                for result in results:
                    output_stream.write(result["address"] + "\n")

        finally:
            if output_file:
                output_stream.close()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully exported {len(results)} addresses to {output_file}"
                    )
                )
            else:
                if format_type != "text":
                    self.stderr.write(
                        self.style.SUCCESS(
                            f"\nSuccessfully exported {len(results)} addresses"
                        )
                    )
