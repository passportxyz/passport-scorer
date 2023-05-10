from account.models import AccountAPIKey, APIKeyPermissions
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill permissions for previously created api keys"

    def handle(self, *args, **kwargs):
        for api_key in AccountAPIKey.objects.all():
            if not api_key.permissions:
                api_key.permissions = APIKeyPermissions.objects.create()
                api_key.save()
