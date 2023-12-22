from django.core.management.base import BaseCommand
from registry.models import Event
import random
import datetime


class Command(BaseCommand):
    help = "Analyze queries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--populate", required=False, help="Populate dummy data", default=False
        )

    address_to_check = "0x96DB2c6D93A8a12089f7a6EdA5474e967308AdEg"
    start = datetime.datetime.fromisoformat("2023-05-10T07:49:08.610198+00:00")
    duration_days = 90
    duration_seconds = duration_days * 24 * 60 * 60

    def populate_dummy_data(self):
        self.stdout.write(self.style.SUCCESS(f"Populating dummy data"))
        addresses = [f"0x{random.randint(0, 2**160):040x}" for _ in range(1000)]
        addresses.append(self.address_to_check)
        context = None

        for set in range(100):
            events = []
            for i in range(10000):
                action = random.choice(Event.Action.choices)[0]
                if action == Event.Action.SCORE_UPDATE:
                    context = random.choice([1, 335])
                events.append(
                    Event(
                        action=random.choice(Event.Action.choices)[0],
                        context=context,
                        address=random.choice(addresses),
                        data={"score": random.random(), "evidence": {"a": 1, "b": 2}},
                        created_at=self.start
                        + datetime.timedelta(
                            seconds=random.randint(0, self.duration_seconds)
                        ),
                    )
                )
            self.stdout.write(self.style.SUCCESS(f"Saving dummy data set {set}"))
            Event.objects.bulk_create(events)

    def analyze_query(self, query):
        self.stdout.write(self.style.SUCCESS(f"Query: {query.query}"))
        self.stdout.write(query.explain(verbose=True, analyze=True) + "\n\n")

    def handle(self, *args, **options):
        if options["populate"]:
            self.populate_dummy_data()

        self.stdout.write(self.style.SUCCESS(f"Analyzing queries"))

        self.stdout.write(self.style.SUCCESS(f"Indexes {Event._meta.indexes}\n\n"))

        test_time = self.start + datetime.timedelta(
            seconds=self.duration_seconds * 3 / 4
        )

        queries = [
            Event.objects.all(),
            Event.objects.filter(
                action=Event.Action.SCORE_UPDATE,
            ),
            Event.objects.filter(
                action=Event.Action.SCORE_UPDATE,
                context=335,
                address=self.address_to_check,
                created_at__lte=test_time,
            ),
            Event.objects.filter(
                action=Event.Action.SCORE_UPDATE,
                context=335,
                created_at__lte=test_time,
            ),
            Event.objects.filter(
                action=Event.Action.SCORE_UPDATE,
                address=self.address_to_check,
                created_at__lte=test_time,
            ),
            Event.objects.filter(
                action=Event.Action.SCORE_UPDATE,
                context=335,
                address=self.address_to_check,
            ),
        ]
        [self.analyze_query(query) for query in queries]
