import os
from io import StringIO

from django.conf import settings
from django.core.management import call_command


# pylint: disable=unused-argument
def handler(event, context):
    """
    Run show migrations command and return the output.
    """
    # Set the settings module if not already set
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
    settings.configure()  # Necessary for Lambda environments

    try:
        output = StringIO()
        call_command("showmigrations", stdout=output)
        return {"statusCode": 200, "body": output.getvalue()}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
