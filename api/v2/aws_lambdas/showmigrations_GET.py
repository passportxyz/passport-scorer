import logging
import subprocess

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)


@with_api_request_exception_handling
def handler(event, context):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Run the Django `showmigrations` command
        logger.info("Received event: %s", event)
        logger.info("Lambda context: %s", vars(context))
        result = subprocess.run(
            ["python", "manage.py", "showmigrations"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Check if there was an error in the command
        if result.returncode != 0:
            logger.error("Error running showmigrations: %s", result.stderr)
            return {
                "statusCode": 500,
                "body": f"Error running showmigrations: {result.stderr}",
            }
        logger.info("showmigrations output: %s", result.stdout)
        # Return the output of `showmigrations`
        return {"statusCode": 200, "body": result.stdout}

    except Exception as e:
        return {"statusCode": 500, "body": f"An error occurred: {str(e)}"}
