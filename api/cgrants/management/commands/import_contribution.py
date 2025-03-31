import json

from django.core.management.base import BaseCommand

from cgrants.models import Contribution


class Command(BaseCommand):
    help = "My shiny new management command."

    def add_arguments(self, parser):
        parser.add_argument("--in", required=True, help="JSONL input file")

    def handle(self, *args, **options):
        input_file = options["in"]
        self.stdout.write(self.style.SUCCESS(f'Input file "{input_file}"'))

        # Load the existing IDs
        existing_ids = set(Contribution.objects.values_list("id", flat=True))

        with open(input_file, encoding="utf-8") as f:
            for _, line in enumerate(f, start=1):
                record = json.loads(line)
                # check that the pk does not yet exist in the list of IDs
                if record["pk"] not in existing_ids:
                    self.stdout.write((f"Creating record with pk={record['pk']}"))
                    s = Contribution(
                        id=record["pk"],
                        subscription_id=record["fields"]["subscription"],
                        data=record,
                    )
                    s.save()
                else:
                    self.stdout.write((f"Skipping record with pk={record['pk']}"))
