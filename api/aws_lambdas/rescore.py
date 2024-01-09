"""
This module provides a handler to manage rescoring requests from an SQS queue in AWS Lambda.
"""

from sys import stdout

from account.models import Community
from aws_lambdas.utils import format_response, with_request_exception_handling
from registry.management.commands.recalculate_scores import recalculate_scores


@with_request_exception_handling
def handler(event, _context):
    """
    Handler for rescore messages from an SQS trigger
    """

    for message in event["Records"]:
        community_ids = message["body"].split(",")
        communities = Community.objects.filter(id__in=community_ids)

        recalculate_scores(
            communities,
            batch_size=1000,
            outstream=stdout,
        )

    return format_response({"status": "success"})
