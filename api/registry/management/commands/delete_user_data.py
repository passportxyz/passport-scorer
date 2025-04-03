from django.core.management.base import BaseCommand

from ceramic_cache.models import CeramicCache, CeramicCacheLegacy
from passport_admin.models import DismissedBanners
from registry.models import Event, HashScorerLink, Passport, Score, Stamp


def delete_objects(query, obj_name, dry_run=True):
    if dry_run:
        print(f"{query.count()} {obj_name} objects would to be deleted")
    else:
        delete_count, _ = query.delete()
        print(f"{delete_count} {obj_name} objects have been deleted")


def delete_all_user_data(eth_address, dry_run=True):
    eth_address = eth_address.lower()
    delete_objects(
        CeramicCache.objects.filter(address=eth_address), "CeramicCache", dry_run
    )
    delete_objects(
        CeramicCacheLegacy.objects.filter(address=eth_address),
        "CeramicCacheLegacy",
        dry_run,
    )

    delete_objects(
        Stamp.objects.filter(passport__address=eth_address), "Stamp", dry_run
    )
    delete_objects(
        Score.objects.filter(passport__address=eth_address), "Score", dry_run
    )
    delete_objects(Passport.objects.filter(address=eth_address), "Passport", dry_run)
    delete_objects(Event.objects.filter(address=eth_address), "Event", dry_run)
    delete_objects(
        HashScorerLink.objects.filter(address=eth_address), "HashScorerLink", dry_run
    )
    delete_objects(
        DismissedBanners.objects.filter(address=eth_address),
        "DismissedBanners",
        dry_run,
    )


class Command(BaseCommand):
    help = """
    Delete user data (usually as per users request).
    This will delete the following objects linked to the specified address:

        CeramicCache
        CeramicCacheLegacy
        Stamp
        Score
        Passport
        Event
        HashScorerLink
        DismissedBanners

    Other data, like Account objects (And all its dependents: AccountAPIKey, Community, ...) are currently not deleted.
    If required please extend this script for those objects as well
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--eth-address", type=str, required=True, help="Eth address for the user"
        )
        parser.add_argument(
            "--exec",
            dest="exec",
            action="store_true",
            help="execute the deletion (default: perform a dry run)",
        )

    def handle(self, *args, **options):
        eth_address = options["eth_address"]
        dry_run = not options["exec"]
        if dry_run:
            print("\n" + "*" * 120)
            print(
                f"\nThis is a dry run for deleting user data for '{eth_address}'. No data will be deleted.\n\n{self.help}"
            )
            print("*" * 120 + "\n")
            delete_all_user_data(eth_address, True)
        else:
            self.stdout.write(self.style.ERROR("\n" + "*" * 120))
            self.stdout.write(
                self.style.ERROR(
                    f"\n   >>> Deleting user data for '{eth_address}'! This is not reversible. Please be careful! <<<"
                )
            )
            self.stdout.write(f"\n\n{self.help}")
            self.stdout.write(self.style.ERROR("*" * 120 + "\n"))
            delete_all_user_data(eth_address, True)
            confirmation = (
                input("\n\nAre you sure you want to delete these objects? (yes/no): ")
                .strip()
                .lower()
            )
            if confirmation == "yes":
                delete_all_user_data(eth_address, False)
            else:
                print("Aborting...")
