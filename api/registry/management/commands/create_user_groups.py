from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Creates default groups"

    def handle(self, *args, **kwargs):
        Group.objects.get_or_create(name="Researcher")
