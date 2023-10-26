from cgrants.models import Contribution, GrantContributionIndex, Profile
from django.core.management.base import BaseCommand
from tqdm import tqdm


class Command(BaseCommand):
    help = "This command will update the contributor_address field in GrantContributionIndex"

    batch_size = 1000

    def handle(self, *args, **options):
        last_id = None
        while True:
            contributions = self.get_data(last_id)

            with tqdm(
                unit="records",
                unit_scale=True,
                desc=f"Aggregating cGrants contributions by address",
            ) as progress_bar:
                if contributions:
                    progress_bar.update(len(contributions))
                    for contribution_index in contributions:
                        last_id = contribution_index.pk
                        try:
                            address = contribution_index.contribution.data["fields"][
                                "originated_address"
                            ]
                        except:
                            address = None
                        contribution_index.contributor_address = address

                    GrantContributionIndex.objects.bulk_update(
                        contributions, ["contributor_address"]
                    )
                else:
                    break  # No more data to process

    def get_data(self, last_id):
        q = (
            GrantContributionIndex.objects.select_related("contribution")
            .all()
            .order_by("id")
        )

        if last_id:
            q = q.filter(id__gt=last_id)

        data = q[: self.batch_size]

        return data
