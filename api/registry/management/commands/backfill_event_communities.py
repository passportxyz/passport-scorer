from django.core.management.base import BaseCommand
from registry.models import Event


class Command(BaseCommand):
    def handle(self, *args, **options):
        batch_size = 1000
        total_events = Event.objects.count()
        self.stdout.write(
            f"Updating the community value for {total_events} event records"
        )
        for start in range(0, total_events, batch_size):
            end = start + batch_size
            batch = Event.objects.filter(action="LDP")[start:end]

            self.stdout.write(f"Updating batch {start} through {end}")
            for event in batch:
                if event.data and "community_id" in event.data:
                    community_id = event.data["community_id"]
                    event.community_id = community_id
                    event.save(update_fields=["community"])

        self.stdout.write(self.style.SUCCESS("Done!"))
