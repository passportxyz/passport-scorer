from io import StringIO

from django.core.management import call_command

# pylint: disable=unused-import
import aws_lambdas.utils


# pylint: disable=unused-argument
def handler(event, context):
    """
    Run show migrations command and return the output.
    """

    try:
        print("Running showmigrations command")
        output = StringIO()
        call_command("showmigrations", stdout=output)
        print("Done running showmigrations command")
        return {"statusCode": 200, "body": output.getvalue()}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
