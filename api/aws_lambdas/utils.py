"""
This module provides utils to manage Passport API requests in AWS Lambda.
"""

import base64
import json
import os
from functools import wraps
from traceback import print_exc
from typing import Any, Dict, Tuple

import boto3
from botocore.exceptions import ClientError
from django.db import (
    DataError,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
os.environ.setdefault("CERAMIC_CACHE_SCORER_ID", "1")

###########################################################
# Loading secrets from secrets manager
# https://aws.amazon.com/developer/language/python/
# For a list of exceptions thrown, see
# https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
# https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
###########################################################


def load_secrets():
    ssm_srn = os.environ["SCORER_SERVER_SSM_ARN"]
    print("Loading secrets from SSM: ", ssm_srn)
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")

    try:
        get_secret_value_response = client.get_secret_value(SecretId=ssm_srn)
    except ClientError as e:
        print(f"Error occurred while loading secret value: {e}")
        print_exc()
        raise e

    # Decrypts secret using the associated KMS key.
    # Load secrets and store them in env variables
    secrets = json.loads(get_secret_value_response["SecretString"])
    for key in secrets:
        os.environ[key] = secrets[key]


if "SCORER_SERVER_SSM_ARN" in os.environ:
    load_secrets()

if "CORE_SECRET_ARN" in os.environ:
    core_secret_arn = os.environ["CORE_SECRET_ARN"]
    print("Loading secrets from SSM: ", core_secret_arn)
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")

    try:
        get_secret_value_response = client.get_secret_value(SecretId=core_secret_arn)
    except ClientError as e:
        print(f"Error occurred while loading secret value: {e}")
        print_exc()
        raise e
    secrets = json.loads(get_secret_value_response["SecretString"])
    db_user = secrets["username"]
    db_password = secrets["password"]
    db_host = secrets["host"]
    db_name = secrets["dbname"]
    db_url = f"psql://{db_user}:{db_password}@{db_host}/{db_name}"
    os.environ["DATABASE_URL"] = db_url

###########################################################
# END: Loading secrets from secrets manager
###########################################################


# pylint: disable=wrong-import-position

import django  # noqa: E402

django.setup()

import api_logging as logging  # noqa: E402

logger = logging.getLogger(__name__)

from django.http import HttpRequest  # noqa: E402
from django_ratelimit.exceptions import Ratelimited  # noqa: E402
from ninja_extra.exceptions import APIException
from ninja_jwt.exceptions import InvalidToken  # noqa: E402
from structlog.contextvars import bind_contextvars  # noqa: E402

from aws_lambdas.exceptions import InvalidRequest  # noqa: E402
from registry.api.utils import (
    ApiKey,
    check_rate_limit,
    get_analysis_api_rate_limited_msg,
    get_passport_api_rate_limited_msg,
    save_api_key_analytics,
)
from registry.exceptions import (  # noqa: E402
    InvalidAddressException,
    NotFoundApiException,
    Unauthorized,
)

RESPONSE_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "Accept,Accept-Encoding,Authorization,Content-Type,Dnt,Origin,User-Agent,X-Csrftoken,X-Requested-With,X-Api-Key",
}


def lambda_to_django_request(api_key, event):
    """
    Convert a Lambda event into a Django HttpRequest object.
    """
    request = HttpRequest()
    request.META["X-Api-Key"] = api_key
    request.path = event["path"]

    return request


def strip_event(event) -> tuple:
    """
    Strips the event of all sensitive fields.
    This will return a tuple like: (sensitive_data_dict, event_without_sensitive_data)
    """
    sensitive_data = {}
    headers = event.get("headers", {})
    if "x-api-key" in headers:
        sensitive_data["x-api-key"] = headers["x-api-key"]
        prefix = headers["x-api-key"].split(".")[0]
        headers["x-api-key"] = f"{prefix}.***"
    return sensitive_data, event


def parse_body(event):
    if event["isBase64Encoded"] and "body" in event and event["body"]:
        body = json.loads(base64.b64decode(event["body"]).decode("utf-8"))
    elif "body" in event and event["body"]:
        body = json.loads(event["body"])
    else:
        body = {}

    return body


def format_response(ret: Any, statusCode=200):
    return {
        "statusCode": statusCode,
        "statusDescription": "200 OK",
        "isBase64Encoded": False,
        "headers": RESPONSE_HEADERS,
        "body": ret.json() if hasattr(ret, "json") else json.dumps(ret),
    }


def with_request_exception_handling(func):
    """
    This wrapper is meant to be used for API handler of the **internal** API, like the ceramic-cache related endpoints
    """

    def wrapper(event, context, *args):
        try:
            bind_contextvars(request_id=context.aws_request_id)

            logger.info("Received event: %s", event)

            return func(event, context, *args)
        except Exception as e:
            if isinstance(e, APIException):
                status = e.status_code
                message = str(e.detail)
            else:
                ratelimit_msg = (
                    get_analysis_api_rate_limited_msg()
                    if event.get("path", "").startswith("/passport/")
                    else get_passport_api_rate_limited_msg()
                )

                error_descriptions: Dict[Any, Tuple[int, str]] = {
                    Unauthorized: (403, "Unauthorized"),
                    InvalidToken: (403, "Invalid token"),
                    InvalidRequest: (400, "Bad request"),
                    Ratelimited: (429, ratelimit_msg),
                    InterfaceError: (500, "DB Error: InterfaceError"),
                    DataError: (500, "DB Error: DataError"),
                    OperationalError: (500, "DB Error: OperationalError"),
                    IntegrityError: (500, "DB Error: IntegrityError"),
                    InternalError: (500, "DB Error: InternalError"),
                    ProgrammingError: (500, "DB Error: ProgrammingError"),
                    NotSupportedError: (500, "DB Error: NotSupportedError"),
                }

                status, message = error_descriptions.get(
                    type(e), (400, "An error has occurred")
                )

            bind_contextvars(
                statusCode=status,
                statusCategory="4XX" if (status >= 400 and status < 500) else "5XX",
            )
            response = {
                "statusCode": status,
                "statusCategory": "4XX" if (status >= 400 and status < 500) else "5XX",
                "statusDescription": str(e),
                "isBase64Encoded": False,
                "headers": RESPONSE_HEADERS,
                "body": json.dumps({"error": message}),
            }

            logger.exception(
                "Error occurred with Passport API. Response: %s", json.dumps(response)
            )
            return response

    return wrapper


def with_api_request_exception_handling(func):
    """
    This wrapper is meant to be used for API handler of the public API like submit-passport
    and analytics request
    """

    @wraps(func)
    def wrapper(_event, context):
        response = None
        error_msg = None
        api_key_id = None
        body = None
        try:
            # First let's bind the context vars for the logger, strip the event from
            # sensitive data and log the event
            bind_contextvars(request_id=context.aws_request_id)
            sensitive_data, event = strip_event(_event)
            logger.info("Received event: %s", event)

            # Authenticate the API request
            api_key = sensitive_data.get("x-api-key", "")
            api_key_instance = ApiKey()
            request = lambda_to_django_request(api_key, event)

            # Authenticate the api key
            user_account = api_key_instance.authenticate(request, api_key)
            api_key_id = request.api_key.id  # we need this in save_api_key_analytics
            if not user_account:
                raise Unauthorized("user_account was not retreived")

            # Check rate limit for the api key
            check_rate_limit(request)

            # Parse the body and call the function
            body = parse_body(event)

            response = format_response(
                func(event, context, request, user_account, body)
            )
        except Exception as e:
            error_msg = str(e)

            if isinstance(e, APIException):
                status = e.status_code
                message = str(e.detail)
            else:
                ratelimit_msg = (
                    get_analysis_api_rate_limited_msg()
                    if event.get("path", "").startswith("/passport/")
                    else get_passport_api_rate_limited_msg()
                )

                error_descriptions: Dict[Any, Tuple[int, str]] = {
                    Unauthorized: (403, "Unauthorized"),
                    InvalidToken: (403, "Invalid token"),
                    InvalidRequest: (400, "Bad request"),
                    InvalidAddressException: (400, "Invalid address"),
                    NotFoundApiException: (400, "Bad request"),
                    Ratelimited: (429, ratelimit_msg),
                    InterfaceError: (500, "DB Error: InterfaceError"),
                    DataError: (500, "DB Error: DataError"),
                    OperationalError: (500, "DB Error: OperationalError"),
                    IntegrityError: (500, "DB Error: IntegrityError"),
                    InternalError: (500, "DB Error: InternalError"),
                    ProgrammingError: (500, "DB Error: ProgrammingError"),
                    NotSupportedError: (500, "DB Error: NotSupportedError"),
                }

                status, message = error_descriptions.get(
                    type(e), (500, "An error has occurred")
                )

            bind_contextvars(
                statusCode=status,
                statusCategory="4XX" if (status >= 400 and status < 500) else "5XX",
            )
            response = {
                "statusCode": status,
                "statusCategory": "4XX" if (status >= 400 and status < 500) else "5XX",
                "statusDescription": str(e),
                "isBase64Encoded": False,
                "headers": RESPONSE_HEADERS,
                "body": json.dumps({"error": message}),
            }
            logger.exception(
                "Error occurred with Passport API. Response: %s", json.dumps(response)
            )

        # Log analytics for the API call
        try:
            if api_key_id:
                save_api_key_analytics(
                    api_key_id=api_key_id,
                    path=event["path"],
                    path_segments=event["path"].split("/")[
                        1:
                    ],  # skip the first element, as it will be the empty string
                    query_params=event["queryStringParameters"],
                    headers=event["headers"],
                    payload=body,
                    response=response.get("body"),
                    response_skipped=False,
                    error=error_msg,
                    status_code=response.get("statusCode"),
                )
        except Exception as e:
            logger.exception(f"Failed to store analytics: {e}")

        return response

    return wrapper


def get_address_param(event):
    if (
        "queryStringParameters" not in event
        or "address" not in event["queryStringParameters"]
    ):
        raise InvalidRequest("Missing address parameter")
    return event["queryStringParameters"]["address"]
