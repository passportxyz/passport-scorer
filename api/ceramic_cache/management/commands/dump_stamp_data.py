import json

import boto3
from cgrants.models import Grant
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Weekly data dump of stamp data since the last dump."

    def handle(self, *args, **options):
        print("Starting dump_stamp_data.py")
