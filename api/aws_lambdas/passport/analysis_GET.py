"""
This module provides a handler to manage API requests in AWS Lambda.
"""

import asyncio
import json
import logging

import aiohttp
from django.db import close_old_connections
from passport.api import (
    EthereumActivityModel,
    PassportAnalysisDetails,
    PassportAnalysisDetailsModels,
    PassportAnalysisResponse,
    handle_get_analysis,
)

from aws_lambdas.utils import (
    with_api_request_exception_handling,
)

log = logging.getLogger(__name__)


async def fetch(session, url, data):
    headers = {"Content-Type": "application/json"}
    async with session.post(url, data=json.dumps(data), headers=headers) as response:
        return await response.text()


async def fetch_all(urls, address):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            task = asyncio.ensure_future(
                fetch(
                    session,
                    url,
                    {"address": address},
                )
            )
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses


urls = [
    "http://core-alb.private.gitcoin.co/eth-stamp-v2-predict",
    "http://core-alb.private.gitcoin.co/nft-model-predict",
    "http://core-alb.private.gitcoin.co/zksync-model-v2-predict",
]


@with_api_request_exception_handling
def _handler(event, _context, _request, _user_account, _body):
    """
    Handles the incoming events and translates them into Django's context.
    """

    address = event["path"].split("/")[-1]

    # analysis = handle_get_analysis(address)

    # return analysis

    loop = asyncio.get_event_loop()
    responses = loop.run_until_complete(fetch_all(urls, address))

    log.debug("responses: %s", json.dumps(responses, indent=2))

    return PassportAnalysisResponse(
        address=address,
        details=PassportAnalysisDetails(
            models=PassportAnalysisDetailsModels(
                ethereum_activity=EthereumActivityModel(score=12.34)
            )
        ),
    )


def handler(*args, **kwargs):
    close_old_connections()
    return _handler(*args, **kwargs)
