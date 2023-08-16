from cgrants.models import Profile
from django.core.management.base import BaseCommand
from django.db.models import Q
from tqdm import tqdm


class Command(BaseCommand):
    help = "This command will extract the github_id for all profiles where it is not yet set."

    def handle(self, *args, **options):
        query = Profile.objects.all().exclude(
            Q(github_id__gt=0) & Q(github_id__isnull=False)
        )
        total_count = query.count()

        self.stdout.write(f"Total number of profiles: {Profile.objects.all().count()}")
        self.stdout.write(f"Num items to process: {total_count}")
        # Process each line of the JSONL file with a progress bar
        last_id = None
        chunk_size = 1000
        num_errors = 0
        num_successes = 0
        with tqdm(
            total=total_count, unit="items", unit_scale=True, desc="Processing profiles"
        ) as pbar:
            has_more = True
            while has_more:
                if last_id:
                    profiles = list(
                        query.filter(id__gt=last_id).order_by("id")[:chunk_size]
                    )
                else:
                    profiles = list(query.filter().order_by("id")[:chunk_size])
                if profiles:
                    last_id = profiles[-1].id
                    for p in profiles:
                        try:
                            p.github_id = p.data["fields"]["data"]["id"]
                            num_successes += 1
                        except Exception as e:
                            num_errors += 1
                    Profile.objects.bulk_update(profiles, ["github_id"])
                    pbar.update(len(profiles))
                else:
                    has_more = False

        self.stdout.write(f"num_errors: {num_errors}")
        self.stdout.write(f"num_successes: {num_successes}")
